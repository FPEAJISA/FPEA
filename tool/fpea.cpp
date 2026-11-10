//===----------------------------------------------------------------------===//
// FPEA — Function Pointer Escape Analysis
//
// Identifies kernel-driver entry points by classifying how each defined
// function's *value* (its address) is used in LLVM IR. A function is an entry
// point when its address escapes the module boundary, so that code outside the
// module can invoke it indirectly, or when it is a module lifecycle routine
// the loader calls by name.
//
// The analysis consults neither pointee types nor struct field offsets, so it
// behaves identically on typed and opaque-pointer IR. It is an approximation
// of the semantic definition from syntactic evidence, not a sound points-to
// analysis; the accompanying paper quantifies where it over- and
// under-approximates.
//
// Escape-evidence signals (see classifyUse):
//   C1  address stored in a global initializer / alias / ifunc
//   C2  module init/exit routine (name, or referenced by an initcall global)
//   C3  address passed as an argument to a direct call
//   C4  address stored to memory
//   C5  address flows through select / phi / return to one of the sinks above
//
// Usage:  fpea <input.bc> <output.json> [--unit]
//   --unit  treat input as a single compilation unit (looser contaminant
//           filter that also drops `name.<number>` clones)
//===----------------------------------------------------------------------===//

#include "llvm/IR/Constants.h"
#include "llvm/IR/GlobalAlias.h"
#include "llvm/IR/GlobalIFunc.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/LLVMContext.h"
#include "llvm/IR/Module.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/raw_ostream.h"

#include <fstream>
#include <map>
#include <regex>
#include <set>
#include <string>
#include <vector>

using namespace llvm;

//===----------------------------------------------------------------------===//
// Symbol filters
//===----------------------------------------------------------------------===//

// Compiler-generated symbols that are not source-level entry points:
// sanitizer/coverage runtime, tracepoint expansions, cloned functions, and
// LLVM/CFI helpers. The unit-level variant additionally drops `name.<number>`
// clones; the link-level variant keeps them, because llvm-link appends numeric
// suffixes to distinct static functions when merging translation units.
static const std::regex ContamUnit(
    R"((\.\d+$|\.(constprop|isra|part|cold)\b|^asan\.|^__asan|^kasan\.)"
    R"(|^__ubsan|^ubsan\.|^__bpf_trace_|^trace_event_raw_event_|^perf_trace_)"
    R"(|^trace_raw_output_|^__traceiter_|^__probestub_|^rcu_lock_|^local_bh_)"
    R"(|^__local_bh_|^llvm\.|^__cfi_|^__pfx_|^__x86_indirect|^__sanitizer_cov))");

static const std::regex ContamLink(
    R"((\.(constprop|isra|part|cold)(\.\d+)?$|^asan\.|^__asan|^kasan\.)"
    R"(|^__ubsan|^ubsan\.|^__bpf_trace_|^trace_event_raw_event_|^perf_trace_)"
    R"(|^trace_raw_output_|^__traceiter_|^__probestub_|^rcu_lock_|^local_bh_)"
    R"(|^__local_bh_|^llvm\.|^__cfi_|^__pfx_|^__x86_indirect|^__sanitizer_cov))");

// Globals emitted by EXPORT_SYMBOL: an address here is a linker artifact, not
// registration into an operation table, so it is not C1 evidence.
static const std::regex ExportArtifact(
    R"((__UNIQUE_ID_+addressable_|\._entry_ptr|\._entry\b|\._entry\.\d))");

static bool isInitcallGlobal(StringRef Name) {
  return Name.startswith("__initcall") || Name.startswith("__exitcall_");
}

//===----------------------------------------------------------------------===//
// Evidence collected per entry-point function
//===----------------------------------------------------------------------===//

namespace {
struct Evidence {
  std::set<std::string> Signals;             // e.g. {"C1", "C3"}
  std::map<std::string, std::string> Where;  // signal -> first witness location
};

class FpeaAnalysis {
public:
  explicit FpeaAnalysis(const std::regex &Contam) : Contam(Contam) {}

  void run(Module &M);
  void writeJson(const std::string &Path) const;
  size_t definedCount() const { return NumDefined; }

private:
  void record(Function *F, const char *Signal, const std::string &Witness) {
    Evidence &E = Result[F];
    E.Signals.insert(Signal);
    E.Where.emplace(Signal, Witness);  // keep first witness only
  }

  bool isClean(const Function &F) const {
    return !std::regex_search(F.getName().str(), Contam);
  }

  // Walk every use of F's value (recursing through constant expressions such
  // as bitcasts and aggregate initializers) and record any escape evidence.
  void classifyUses(Function *F);

  // True if a value produced by a select/phi eventually reaches a sink that
  // lets the address escape: a store value, a call argument, or a return.
  // A value used only as a call's *callee* is invoked in place and does not
  // escape.
  static bool reachesSink(Instruction *Seed);

  const std::regex &Contam;
  std::map<Function *, Evidence> Result;
  size_t NumDefined = 0;
};
}  // namespace

bool FpeaAnalysis::reachesSink(Instruction *Seed) {
  std::vector<Value *> Work{Seed};
  std::set<Value *> Seen{Seed};
  while (!Work.empty()) {
    Value *Cur = Work.back();
    Work.pop_back();
    for (User *U : Cur->users()) {
      if (isa<SelectInst>(U) || isa<PHINode>(U)) {
        if (Seen.insert(U).second)
          Work.push_back(U);
      } else if (auto *SI = dyn_cast<StoreInst>(U)) {
        if (SI->getValueOperand() == Cur)
          return true;
      } else if (isa<ReturnInst>(U)) {
        return true;
      } else if (auto *CB = dyn_cast<CallBase>(U)) {
        for (Value *Arg : CB->args())
          if (Arg == Cur)
            return true;
      }
    }
  }
  return false;
}

void FpeaAnalysis::classifyUses(Function *F) {
  // C2 by name: the loader calls these directly, so the address need not
  // appear as a value anywhere.
  if (F->getName() == "init_module" || F->getName() == "cleanup_module")
    record(F, "C2", "name");

  std::vector<Value *> Work{F};
  std::set<Value *> Seen{F};
  while (!Work.empty()) {
    Value *V = Work.back();
    Work.pop_back();
    for (User *U : V->users()) {
      // blockaddress(@F, %bb) is the address of a basic block, not an escape
      // of the function's address.
      if (isa<BlockAddress>(U))
        continue;

      // C1: initializer of a global variable / alias / ifunc.
      if (auto *GV = dyn_cast<GlobalVariable>(U)) {
        std::string Name = GV->getName().str();
        if (!std::regex_search(Name, ExportArtifact))
          record(F, "C1", Name);
        if (isInitcallGlobal(GV->getName()))
          record(F, "C2", Name);
        continue;
      }
      if (auto *GA = dyn_cast<GlobalAlias>(U)) {
        std::string Name = GA->getName().str();
        if (!std::regex_search(Name, ExportArtifact))
          record(F, "C1", Name);
        continue;
      }
      if (auto *GI = dyn_cast<GlobalIFunc>(U)) {
        record(F, "C1", GI->getName().str());
        continue;
      }

      // Constant expressions (bitcast, GEP, aggregate constants) are not
      // themselves evidence; recurse to their users to find the real consumer.
      if (isa<Constant>(U)) {
        if (Seen.insert(U).second)
          Work.push_back(U);
        continue;
      }

      auto *I = dyn_cast<Instruction>(U);
      if (!I)
        continue;
      std::string Loc = I->getFunction() ? I->getFunction()->getName().str() : "?";

      if (auto *CB = dyn_cast<CallBase>(I)) {
        // C3: passed as an argument to a *direct* call to some other function.
        // stripPointerCasts handles typed IR, where the callee is reached
        // through a bitcast constant expression.
        bool IsArg = false;
        for (Value *Arg : CB->args())
          if (Arg == V)
            IsArg = true;
        auto *Callee =
            dyn_cast<Function>(CB->getCalledOperand()->stripPointerCasts());
        if (IsArg && Callee && Callee != F)
          record(F, "C3", Callee->getName().str());
        continue;
      }
      if (auto *SI = dyn_cast<StoreInst>(I)) {
        // C4: stored as the value operand (not the address operand).
        if (SI->getValueOperand() == V)
          record(F, "C4", Loc);
        continue;
      }
      if (isa<ReturnInst>(I)) {
        record(F, "C5", "ret@" + Loc);
        continue;
      }
      if (isa<SelectInst>(I) || isa<PHINode>(I)) {
        // C5: only if the selected/merged value later reaches an escaping sink.
        if (reachesSink(I))
          record(F, "C5", "selphi@" + Loc);
        continue;
      }
      // Any other use (icmp, ptrtoint feeding a comparison, ...) is not
      // escape evidence.
    }
  }
}

void FpeaAnalysis::run(Module &M) {
  std::vector<Function *> Clean;
  for (Function &F : M) {
    if (F.isDeclaration())
      continue;
    ++NumDefined;
    if (isClean(F))
      Clean.push_back(&F);
  }
  for (Function *F : Clean)
    classifyUses(F);
}

//===----------------------------------------------------------------------===//
// JSON output
//===----------------------------------------------------------------------===//

static std::string jsonEscape(std::string S) {
  std::string Out;
  Out.reserve(S.size());
  for (char C : S) {
    if (C == '"' || C == '\\')
      Out += '\\';
    Out += C;
  }
  return Out;
}

void FpeaAnalysis::writeJson(const std::string &Path) const {
  std::ofstream O(Path);
  O << "{\"defined\":" << NumDefined
    << ",\"entries\":{";
  bool FirstFn = true;
  for (const auto &KV : Result) {
    if (!FirstFn)
      O << ",";
    FirstFn = false;
    O << "\"" << jsonEscape(KV.first->getName().str()) << "\":{";
    bool FirstSig = true;
    for (const std::string &Sig : KV.second.Signals) {
      if (!FirstSig)
        O << ",";
      FirstSig = false;
      O << "\"" << Sig << "\":\""
        << jsonEscape(KV.second.Where.at(Sig)) << "\"";
    }
    O << "}";
  }
  O << "}}\n";
}

//===----------------------------------------------------------------------===//

int main(int argc, char **argv) {
  if (argc < 3) {
    errs() << "usage: fpea <input.bc> <output.json> [--unit]\n";
    return 1;
  }
  bool Unit = (argc > 3 && std::string(argv[3]) == "--unit");

  LLVMContext Ctx;
  SMDiagnostic Err;
  std::unique_ptr<Module> M = parseIRFile(argv[1], Err, Ctx);
  if (!M) {
    Err.print("fpea", errs());
    return 2;
  }

  FpeaAnalysis Analysis(Unit ? ContamUnit : ContamLink);
  Analysis.run(*M);
  Analysis.writeJson(argv[2]);
  return 0;
}
