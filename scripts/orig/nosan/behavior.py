"""Behaviour classification of the link-layer FPEA entry points (LLVM 14).

Reuses measure_c5r.py (signals, regexes, job(), input listing); for every unit it labels
each entry point by the enclosing struct of its C1 use, the C3 callee or the C4 store target,
maps the labels to behaviour classes and picks one representative class by priority.
Invoked as `python3 behavior.py > behavior.log` from this folder; writes behavior.json.
"""
import re
import subprocess
import json
from multiprocessing import Pool
from collections import Counter, defaultdict

from measure_c5r import DIS, CONTAM, EXP, SYM, job, list_input_files

# Struct families (names without the 'struct.'/'union.' prefix) used by klass().
USER = {
    'file_operations', 'proc_ops', 'block_device_operations', 'tty_operations',
    'seq_operations', 'proto_ops', 'v4l2_file_operations', 'v4l2_ioctl_ops', 'snd_pcm_ops',
    'snd_kcontrol_new', 'fb_ops', 'drm_ioctl_desc', 'vm_operations_struct',
    'device_attribute', 'attribute', 'kobj_attribute', 'bin_attribute',
    'sensor_device_attribute', 'sensor_device_attribute_2', 'driver_attribute',
    'class_attribute', 'bus_attribute', 'iio_dev_attr', 'iio_chan_spec_ext_info',
    'dev_ext_attribute', 'kernel_param_ops'}
LIFE = {
    'platform_driver', 'pci_driver', 'i2c_driver', 'spi_driver', 'usb_driver',
    'device_driver', 'hid_driver', 'dev_pm_ops', 'sdio_driver', 'serio_driver', 'acpi_driver',
    'amba_driver', 'pcmcia_driver', 'virtio_driver', 'mdio_driver', 'phy_driver',
    'of_device_id', 'bus_type', 'class', 'device_type', 'module'}
NET = {
    'net_device_ops', 'ethtool_ops', 'header_ops', 'ieee80211_ops', 'cfg80211_ops',
    'dcbnl_rtnl_ops', 'xfrmdev_ops', 'switchdev_ops', 'dsa_switch_ops', 'phylink_mac_ops',
    'rtnl_link_ops', 'napi_struct'}
DEFER = {
    'work_struct', 'delayed_work', 'timer_list', 'hrtimer', 'tasklet_struct', 'rcu_head',
    'kthread_work', 'irq_work', 'callback_head'}
COMPL = {
    'urb', 'bio', 'scatterlist', 'dma_async_tx_descriptor', 'completion', 'usb_request',
    'request'}
# C3 callee families.
IRQAPI = re.compile(
    r'(request(_threaded)?_irq|devm_request(_threaded|_any_context)?_irq|pcmcia_request_irq'
    r'|bind_\w*irqhandler|request_percpu_irq|irq_set_chained_handler\w*'
    r'|request_any_context_irq|__irq_set_handler)')
DEFAPI = re.compile(
    r'(init_timer_key|hrtimer_init|tasklet_init|tasklet_setup|__init_work|init_work|INIT_WORK'
    r'|call_rcu|kthread_create\w*|queue_work\w*|mod_timer|__kthread_create\w*|timer_setup'
    r'|irq_work_init)')
TEAR = re.compile(r'(devm_add_action(_or_reset)?|devm_add_action_or_reset|__devm_add_action\w*)')
NOTIF = re.compile(r'(register_\w*notifier\w*|\w*_notifier_chain_register)')
# Behaviour classes, most specific first; an entry point gets the first class it matches.
PRI = ['interrupt', 'deferred', 'completion', 'teardown', 'user-triggered', 'network-stack',
       'lifecycle', 'lifecycle/bus', 'notifier', 'framework-optable', 'api-registration',
       'unlabeled']


def enclosing_struct(line, pos):
    """Name of the innermost named struct/union whose '{' encloses position pos of a global
    initialiser line (anonymous {..} aggregates are skipped outward); None if not found."""
    d = 0
    i = pos
    while i > 0:
        i -= 1
        ch = line[i]
        if ch == '}':
            d += 1
        elif ch == '{':
            if d == 0:
                m = re.search(r'%(struct\.[\w.]+|union\.[\w.]+)\s*$', line[:i])
                if m:
                    return re.sub(r'\.\d+$', '', m.group(1))
                # anonymous {..} : keep going outward
            else:
                d -= 1
    return None


def labels(p):
    """Label every address-taken use of a defined function in unit p.

    Returns (c, lab, at_kind): defined functions, {function: {(signal, detail)}} where
    detail is the enclosing struct (C1), the callee (C3) or the store target (C4), and
    {function: {usage kind}} for all address-taken uses.
    """
    ll = subprocess.run([DIS, '-o', '-', p], capture_output=True, text=True, timeout=900).stdout
    c = {x for x in re.findall(r'^define[^@]*@([\w.$]+)\(', ll, re.M) if not CONTAM.search(x)}
    lab = defaultdict(set)
    at_kind = defaultdict(set)
    gep = {}                        # %v -> (struct, field index) of getelementptr results
    for line in ll.split('\n'):
        if line.startswith('define'):
            gep = {}
        if line.startswith('!') or line.startswith(';'):
            continue
        L = line.strip()
        mg = (re.match(r'(%[\w.$]+)\s*=\s*getelementptr\b[^,]*?(%(?:struct|union)\.[\w.]+)'
                       r'\s*,[^\n]*?,\s*i32\s+(\d+)\s*$', L)
              or re.match(r'(%[\w.$]+)\s*=\s*getelementptr\b[^,]*?(%(?:struct|union)\.[\w.]+)'
                          r'\s*,.*?i32 (\d+)(?:,|$)', L))
        if mg:
            gep[mg.group(1)] = (re.sub(r'\.\d+$', '', mg.group(2)[1:]), mg.group(3))
        for mm in SYM.finditer(line):
            a = mm.group(1)
            if a not in c:
                continue
            if line.startswith('@'):
                if EXP.search(line.split('=')[0]):
                    continue
                s = enclosing_struct(line, mm.start())
                lab[a].add(('C1', s or 'anon/array'))
                at_kind[a].add('global')
            elif L.startswith('store'):
                md = re.match(r'store\s+ptr\s+@' + re.escape(a)
                              + r'\s*,\s*ptr\s+(%[\w.$]+|@[\w.$]+'
                              r'|getelementptr[^,]*,\s*ptr\s+@[\w.$]+[^)]*\))', L)
                dst = '?'
                if md:
                    t = md.group(1)
                    if t in gep:
                        dst = f"{gep[t][0]}#{gep[t][1]}"
                    elif t.startswith('@'):
                        dst = 'global-var'
                    else:
                        mi = re.search(r'getelementptr[^,]*?%((?:struct|union)\.[\w.]+)', t)
                        if mi:
                            dst = re.sub(r'\.\d+$', '', mi.group(1)) + '#const'
                lab[a].add(('C4', dst))
                at_kind[a].add('store')
            elif re.match(r'(%\S+\s*=\s*)?icmp\b', L):
                at_kind[a].add('icmp')
            elif re.match(r'(%\S+\s*=\s*)?(select|phi)\b', L):
                at_kind[a].add('select/phi')
            elif re.match(r'ret\b', L):
                at_kind[a].add('ret')
            elif re.search(r'\bcall\b', L):
                mc = re.search(r'@([\w.$]+)\(', L)
                if mc and mc.group(1) != a:
                    lab[a].add(('C3', mc.group(1)))
                    at_kind[a].add('callarg')
                else:
                    at_kind[a].add('call-other')
            else:
                at_kind[a].add('other')
    return c, lab, at_kind


def job2(p):
    """Pool worker: FPEA signals (measure_c5r.job) plus the labels of unit p."""
    r = job(p)
    if not r:
        return None
    path, c, dec, sig, ctx, W = r
    try:
        c2, lab, atk = labels(p)
    except Exception:
        return None
    return sig, lab, atk


def klass(l):
    """Behaviour class of one (signal, detail) label."""
    k, v = l
    if k == 'C2':
        return 'lifecycle'
    if k == 'C1':
        s = (v or '').replace('struct.', '').replace('union.', '')
        if s in USER:
            return 'user-triggered'
        if s in LIFE:
            return 'lifecycle/bus'
        if s in NET:
            return 'network-stack'
        if s in DEFER:
            return 'deferred'
        if s in COMPL:
            return 'completion'
        if s == 'notifier_block':
            return 'notifier'
        if s == 'anon/array':
            return 'unlabeled'
        return 'framework-optable'
    if k == 'C3':
        if IRQAPI.search(v):
            return 'interrupt'
        if DEFAPI.search(v):
            return 'deferred'
        if TEAR.search(v):
            return 'teardown'
        if NOTIF.search(v):
            return 'notifier'
        return 'api-registration'
    if k == 'C4':
        s = v.split('#')[0].replace('struct.', '').replace('union.', '')
        if s in DEFER:
            return 'deferred'
        if s in COMPL:
            return 'completion'
        if s in USER:
            return 'user-triggered'
        if s in NET:
            return 'network-stack'
        if s in LIFE:
            return 'lifecycle/bus'
        if v in ('?', 'global-var'):
            return 'unlabeled'
        return 'framework-optable'
    return 'unlabeled'


def main():
    """Classify all link-layer entry points, print the distribution, write behavior.json."""
    files = list_input_files()
    cls = Counter()                 # representative class -> count
    multi = Counter()               # number of distinct (labelled) classes -> count
    nF = 0                          # FPEA entry points
    atx = Counter()                 # usage-form combinations of address-taken non-FPEA
    nATX = 0
    top = defaultdict(Counter)      # class -> detail -> count
    ex = {}
    with Pool(14) as pl:
        for r in pl.imap_unordered(job2, files, chunksize=8):
            if not r:
                continue
            sig, lab, atk = r
            for f, s in sig.items():
                nF += 1
                L = set(lab.get(f, set()))
                if 'C2' in s:
                    L.add(('C2', 'init/exit'))
                ks = {klass(x) for x in L} or {'unlabeled'}
                best = min(ks, key=lambda k: PRI.index(k))
                cls[best] += 1
                if len(ks - {'unlabeled'}) > 1:
                    multi[len(ks - {'unlabeled'})] += 1
                for x in L:
                    if klass(x) == best:
                        top[best][x[1]] += 1
                ex.setdefault(best, []).append(f)
            for f, kinds in atk.items():
                if f in sig:
                    continue
                nATX += 1
                atx[' + '.join(sorted(kinds))] += 1
    print(f"=== Behaviour classification of {nF} FPEA entry points"
          f" (one representative by priority) ===")
    for k in PRI:
        if cls[k]:
            top_str = ', '.join(f'{a}({b})' for a, b in top[k].most_common(4))
            print(f"  {k:18} {cls[k]:7}  {cls[k]/nF*100:5.1f}%   top: {top_str}")
    lab_ok = nF - cls['unlabeled']
    print(f"  → behaviour label assigned {lab_ok} ({lab_ok/nF*100:.1f}%),"
          f"  entry points with multiple behaviours {sum(multi.values())}")
    print(f"\n=== address-taken but not FPEA: {nATX} — usage forms ===")
    for k, n in atx.most_common(8):
        print(f"  {k:28} {n:6}  {n/nATX*100:5.1f}%")
    result = dict(nF=nF, cls=dict(cls), top={k: dict(v.most_common(15)) for k, v in top.items()},
                  atx=dict(atx), nATX=nATX)
    with open('behavior.json', 'w') as fh:
        json.dump(result, fh, indent=1)


if __name__ == '__main__':
    main()
