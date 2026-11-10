"""Batch generation of the paper figures: fig1 overview, fig3 literal/placeholder, fig4 offset
heatmap, fig5 UAFX per-kind trend, fig6 subsystem share, fig7 per-stratum precision.

Inputs: ~/epi_regfn/handler_offset.json and version_results / subsystem_ratio /
final_result_expert / strata_pop .json in /home/user/fpea_gt/final.
Output: figures/<name>.{pdf,png,svg} (DejaVu font, compressed) + figures/ascii/<name>.pdf
(core fonts, uncompressed, pure ASCII, for text upload to Drive).
Invoked as `python3 fig_all.py` (pdf/png/svg) and `python3 fig_all.py ascii` (ascii pdf).
"""
import json
import math
import os
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch  # noqa: E402

F = '/home/user/fpea_gt/final'
OUT = f'{F}/figures'
HANDLER_OFFSET_JSON = os.path.expanduser('~/epi_regfn/handler_offset.json')
ASCII = len(sys.argv) > 1 and sys.argv[1] == 'ascii'
VERS = ['5.17.11', '5.19.17', '6.9', '7.1.4']
HEADER_VERS = ['5.17', '5.19', '6.9', '7.1']

# fig3 data: named vs literal file_operations globals and units with a {} placeholder
# (counts / unit totals per version, from literal_struct_scan / placeholder_scan)
NAMED = [2102, 2140, 1102]
LITERAL = [12, 12, 1347]
PLACEHOLDER_PCT = [28/15522*100, 28/15913*100, 11451/17579*100]
# fig4 rows: (struct, handler) whose field index is shown
OFFSET_ROWS = [
    ('file_operations', 'llseek'), ('file_operations', 'read'), ('file_operations', 'write'),
    ('file_operations', 'unlocked_ioctl'), ('file_operations', 'compat_ioctl'),
    ('file_operations', 'mmap'), ('file_operations', 'open'), ('file_operations', 'release'),
    ('pci_driver', 'probe'), ('pci_driver', 'remove'), ('pci_driver', 'suspend'),
    ('pci_driver', 'resume'), ('pci_driver', 'shutdown'), ('pci_driver', 'err_handler'),
    ('net_device_ops', 'ndo_open'), ('net_device_ops', 'ndo_validate_addr'),
    ('block_device_operations', 'rw_page'), ('platform_driver', 'probe'),
    ('platform_driver', 'remove'), ('device_driver', 'probe'),
]
# fig5: UAFX rule kinds, legend labels and colours
KINDS = ['READ_HDR', 'WRITE_HDR', 'MY_IOCTL', 'IOCTL_CAND', 'INT_HANDLER_T']
KIND_LABEL = {'READ_HDR': 'READ_HDR (name+index)', 'WRITE_HDR': 'WRITE_HDR (name+index)',
              'MY_IOCTL': 'MY_IOCTL (name+index)', 'IOCTL_CAND': 'IOCTL_CAND (signature)',
              'INT_HANDLER_T': 'INT_HANDLER_T (signature)'}
KIND_COLOR = {'READ_HDR': '#c53030', 'WRITE_HDR': '#dd6b20', 'MY_IOCTL': '#b7791f',
              'IOCTL_CAND': '#718096', 'INT_HANDLER_T': '#2b6cb0'}
# fig6: overall entry-point share of all drivers (entry points / defined functions)
ALL_DRIVERS_RATIO = 129967/242823*100
# fig7: strata in display order
STRATA = ['C1', 'C4only', 'C3', 'C5']


def setup_rcparams():
    if ASCII:
        plt.rcParams.update({'font.family': 'Helvetica', 'pdf.use14corefonts': True,
                             'pdf.compression': 0})
    else:
        plt.rcParams.update({'font.family': 'DejaVu Sans'})
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})


def save(fig, name):
    """Save a figure: pdf/png/svg, or (ascii mode) a pure-ASCII uncompressed pdf."""
    if ASCII:
        p = f'{OUT}/ascii/{name}.pdf'
        fig.savefig(p, bbox_inches='tight')
        b = bytearray(open(p, 'rb').read())
        # replace the 4-byte binary comment on line 2 with ASCII of the same length to obtain
        # a pure-ASCII PDF (xref offsets unchanged)
        for k in range(len(b)):
            if b[k] >= 128:
                b[k] = ord('z')
        with open(p, 'wb') as fp:
            fp.write(b)
    else:
        for ext in ('pdf', 'png', 'svg'):
            fig.savefig(f'{OUT}/{name}.{ext}', dpi=300, bbox_inches='tight')
    plt.close(fig)


# ---------- fig1: overview ----------
def box(ax, x, y, w, h, text, fc='#edf2f7', ec='#2d3748', fs=8, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle='round,pad=0.4,rounding_size=1.2',
                                fc=fc, ec=ec, lw=1))
    ax.text(x+w/2, y+h/2, text, ha='center', va='center', fontsize=fs,
            fontweight='bold' if bold else 'normal', linespacing=1.25)


def arrow(ax, x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle='-|>', mutation_scale=10, lw=1,
                                 color='#2d3748'))


def fig1_overview():
    fig, ax = plt.subplots(figsize=(7.2, 2.9))
    ax.axis('off')
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 44)
    box(ax, 1, 16, 14, 12, 'Driver unit\n(.c -> .o.bc)\nLLVM 14 typed\nLLVM 16 opaque', fs=6.8)
    box(ax, 19, 13, 34, 18, 'Function Pointer Escape Analysis\nC1 global initializer\n'
        'C2 init_module / cleanup_module, initcall\nC3 call argument      C4 store operand\n'
        'C5 select / phi / ret, then sink', fc='#ebf8ff', fs=6.8)
    box(ax, 57, 16, 17, 12,
        'Compiler-symbol filter\nsanitizer, tracepoint,\nclone, EXPORT artifact', fs=6.5)
    box(ax, 78, 25, 21, 9, 'Entry-point set\nno list, type or layout', fc='#f0fff4', fs=6.8,
        bold=True)
    box(ax, 78, 9, 21, 9, 'UAFX, unmodified\ncross-entry UAF detection', fc='#fffaf0', fs=6.8)
    arrow(ax, 15, 22, 19, 22)
    arrow(ax, 53, 22, 57, 22)
    arrow(ax, 74, 22, 78, 28)
    arrow(ax, 88.5, 25, 88.5, 18)
    ax.text(40, 4.5, 'Escape-as-entry: a function can be called from outside only if its address '
            'leaves the unit,\nand that act is observable in IR independent of struct names, '
            'field indices and pointer types.', ha='center', va='center', fontsize=7,
            color='#4a5568')
    save(fig, 'fig1_overview')


# ---------- fig3: named vs literal + placeholder units ----------
def fig3_literal_struct():
    named = NAMED
    lit = LITERAL
    ph = PLACEHOLDER_PCT
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 2.5), gridspec_kw=dict(width_ratios=[1.1, 1]))
    x = range(3)
    w = 0.38
    vs = VERS[:3]
    a.bar([i-w/2 for i in x], named, w, color='#2b6cb0',
          label='named  %struct.file_operations { ... }')
    a.bar([i+w/2 for i in x], lit, w, color='#c53030',
          label='literal  { %struct.module*, ... } { ... }')
    for i in x:
        a.text(i-w/2, named[i]+40, f'{named[i]:,}', ha='center', fontsize=7.5, color='#2b6cb0')
        a.text(i+w/2, lit[i]+40, f'{lit[i]:,}', ha='center', fontsize=7.5, color='#c53030')
    a.set_xticks(list(x))
    a.set_xticklabels(vs)
    a.set_ylim(0, 3300)
    a.set_ylabel('file_operations globals (clang 14)')
    a.legend(frameon=False, fontsize=7, loc='upper center', ncol=1)
    a.set_title('(a) How clang emits file_operations initializers', fontsize=9, loc='left')
    b.bar(list(x), ph, 0.5, color='#718096')
    for i in x:
        b.text(i, ph[i]+2, f'{ph[i]:.1f}%', ha='center', fontsize=8)
    b.set_xticks(list(x))
    b.set_xticklabels(vs)
    b.set_ylim(0, 80)
    b.set_ylabel('Units with {}* placeholder in\n%struct.file_operations (%)')
    b.set_title('(b) Placeholder in %struct.file_operations', fontsize=9, loc='left')
    b.text(0, 8, '28 /\n15,522', ha='center', fontsize=7, color='#4a5568')
    b.text(1, 8, '28 /\n15,913', ha='center', fontsize=7, color='#4a5568')
    b.text(2, 72, '11,451 / 17,579', ha='center', fontsize=7, color='#4a5568')
    save(fig, 'fig3_literal_struct')


# ---------- fig4: handler offset heatmap ----------
def fig4_offset_drift():
    H = json.load(open(HANDLER_OFFSET_JSON))
    rows = OFFSET_ROWS
    hv = HEADER_VERS
    M = [[(H[s][v].index(f) if f in H[s][v] else None) for v in hv] for s, f in rows]
    fig, ax = plt.subplots(figsize=(4.6, 5.2))
    base = [r[0] for r in M]
    for i, r in enumerate(M):
        for j, v in enumerate(r):
            if v is None:
                col = '#e2e8f0'
                t = 'gone'
            elif v == base[i]:
                col = '#c6f6d5'
                t = str(v)
            else:
                col = '#fed7d7'
                t = f'{v}'
            ax.add_patch(plt.Rectangle((j, len(M)-1-i), 1, 1, fc=col, ec='white'))
            ax.text(j+0.5, len(M)-1-i+0.5, t, ha='center', va='center', fontsize=8,
                    color='#1a202c')
    ax.set_xlim(0, 4)
    ax.set_ylim(0, len(M))
    ax.set_xticks([k+0.5 for k in range(4)])
    ax.set_xticklabels(['5.17', '5.19', '6.9', '7.1'])
    ax.set_yticks([len(M)-1-i+0.5 for i in range(len(M))])
    ax.set_yticklabels([f'{s}.{f}' for s, f in rows], fontsize=7.5)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_title('Field index of op-table handlers (source headers)\n'
                 'green = unchanged vs 5.17, red = moved, gray = removed', fontsize=8.5, loc='left')
    save(fig, 'fig4_offset_drift')


# ---------- fig5: UAFX kinds trend ----------
def fig5_uafx_kinds():
    vr = json.load(open(f'{F}/version_results.json'))
    kinds = KINDS
    lab = KIND_LABEL
    cols = KIND_COLOR
    fig, ax = plt.subplots(figsize=(4.8, 3.3))
    for k in kinds:
        ys = [vr[v]['baseline_kinds'].get(k, 0) for v in VERS[:3]]
        ax.plot(range(3), ys, 'o-' if 'index' in lab[k] else 's--', color=cols[k], label=lab[k],
                lw=1.5)
        ax.text(2.07, ys[2]+(40 if k == 'READ_HDR' else -40 if k == 'WRITE_HDR' else 0),
                f'{ys[2]:,}', fontsize=7, va='center', color=cols[k])
    ax.set_xticks(range(3))
    ax.set_xticklabels(VERS[:3])
    ax.set_xlim(-0.2, 2.5)
    ax.set_ylabel('Entry points reported by UAFX (unit layer)')
    ax.legend(frameon=False, fontsize=6.8, loc='upper center', bbox_to_anchor=(0.45, -0.16), ncol=2)
    ax.set_title('UAFX output per rule kind; name+index kinds drop in 6.9', fontsize=8.5,
                 loc='left')
    save(fig, 'fig5_uafx_kinds')


# ---------- fig6: subsystem ratio ----------
def fig6_subsystem_ratio():
    sub = json.load(open(f'{F}/subsystem_ratio.json'))
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    names = [s['subsystem'] for s in sub]
    vals = [s['ratio'] for s in sub]
    ax.bar(range(len(sub)), vals, color=['#2b6cb0' if v >= 53.5 else '#a0aec0' for v in vals])
    ax.axhline(ALL_DRIVERS_RATIO, color='#c53030', lw=1, ls='--')
    ax.text(len(sub)-0.5, ALL_DRIVERS_RATIO+1.5, 'all drivers 53.5%', ha='right', fontsize=7.5,
            color='#c53030')
    ax.set_xticks(range(len(sub)))
    ax.set_xticklabels(names, rotation=60, ha='right', fontsize=7)
    ax.set_ylabel('FPEA entry points / defined functions (%)')
    ax.set_ylim(0, 100)
    ax.set_title('Entry-point share by subsystem '
                 '(5.17.11, subsystems with >= 1,000 defined functions)', fontsize=8.5, loc='left')
    save(fig, 'fig6_subsystem_ratio')


# ---------- fig7: precision by stratum ----------
def wilson(k, n, z=1.96):
    """Wilson score interval for k successes out of n."""
    p = k/n
    d = 1+z*z/n
    c = (p+z*z/(2*n))/d
    h = z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return (c-h, c+h)


def fig7_precision_strata():
    fr = json.load(open(f'{F}/final_result_expert.json'))
    W = json.load(open(f'{F}/strata_pop.json'))['W_true']
    order = STRATA
    fig, ax = plt.subplots(figsize=(4.6, 2.6))
    for i, s in enumerate(order):
        tp, fp = fr['byst'][s]
        n = tp+fp
        p = tp/n
        lo, hi = wilson(tp, n)
        ax.errorbar(i, p, yerr=[[p-lo], [hi-p]], fmt='o', color='#2b6cb0', capsize=3)
        ax.text(i, hi+0.025, f'{p:.3f}\nn={n}, w={W[s]:.3f}', ha='center', fontsize=6.8)
    ax.axhline(fr['wprec_all'], color='#c53030', ls='--', lw=1)
    ax.text(-0.45, fr['wprec_all']+0.012, f'weighted {fr["wprec_all"]:.3f}', ha='left',
            fontsize=7.5, color='#c53030')
    ax.axhline(fr['prec_simple'], color='#718096', ls=':', lw=1)
    ax.text(-0.45, fr['prec_simple']-0.045, f'simple {fr["prec_simple"]:.3f}', ha='left',
            fontsize=7.5, color='#718096')
    ax.set_xticks(range(4))
    ax.set_xticklabels(['C1 (global init)', 'C4 only (store)', 'C3 (call arg)',
                        'C5 (select/phi/ret)'], fontsize=7.5)
    ax.set_ylim(0.45, 1.1)
    ax.set_xlim(-0.5, 3.5)
    ax.set_ylabel('Precision (expert reference set)')
    ax.set_title('Precision per stratum with Wilson 95% CI', fontsize=8.5, loc='left')
    save(fig, 'fig7_precision_strata')


def main():
    os.makedirs(f'{OUT}/ascii', exist_ok=True)
    setup_rcparams()
    fig1_overview()
    fig3_literal_struct()
    fig4_offset_drift()
    fig5_uafx_kinds()
    fig6_subsystem_ratio()
    fig7_precision_strata()
    print('done', ASCII)


if __name__ == '__main__':
    main()
