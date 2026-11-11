"""Figure 2: FPEA/UAFX entry-point counts per version (bars) + rule semantic hit rate (line).
The two panels are stacked vertically so that the figure fits one column of the two-column
manuscript (3.3 in wide); until v3.1 they were side by side in a two-column figure.

Sources: version_results.json, semantic_hit_<ver>.json in
$FPEA_HOME/fpea_gt/final.  Output: figures/fig2_version_stability.{pdf,png,svg} there and the
plotted numbers on stdout.  Invoked as `python3 fig2.py`.
"""
import os
import json
import matplotlib

# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
HOME_ROOT = os.environ.get('FPEA_HOME') or os.path.expanduser('~')
TMP_ROOT = os.environ.get('FPEA_TMP', '/tmp')
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

F = f'{HOME_ROOT}/fpea_gt/final'
VERS = ['5.17.11', '5.19.17', '6.9', '7.1.4']
# 7.1.4 numbers come from the non-randstruct build
KEY = {'7.1.4': '7.1.4-norand'}
C_FPEA = '#2b6cb0'
C_UAFX = '#c05621'
BAR_W = 0.38


def load_data():
    """Plotted series: (fpea, uafx, miss, semantic, simple, rand)."""
    vr = json.load(open(f'{F}/version_results.json'))
    fpea = [vr[KEY.get(v, v)]['FPEA'] for v in VERS]
    uafx = [vr[v]['baseline'] if vr[v]['baseline'] else None for v in VERS]
    miss = [vr[v]['miss_rate'] if vr[v]['baseline'] else None for v in VERS]
    sem = {v: json.load(open(f'{F}/semantic_hit_{KEY.get(v, v)}.json')) for v in VERS}
    semantic = [sem[v]['rate_semantic_within_header'] for v in VERS]
    simple = [sem[v]['rate_has_fn'] for v in VERS]
    rand = json.load(open(f'{F}/semantic_hit_7.1.4.json'))['rate_has_fn']
    return fpea, uafx, miss, semantic, simple, rand


def draw_coverage(a, fpea, uafx, miss):
    """(a) entry-point counts per version, FPEA vs UAFX whitelist."""
    x = range(len(VERS))
    w = BAR_W
    c_f, c_u = C_FPEA, C_UAFX
    a.bar([i-w/2 for i in x], fpea, w, color=c_f, label='FPEA (escape-as-entry)')
    a.bar([i+w/2 for i in x], [u or 0 for u in uafx], w, color=c_u,
          label='UAFX whitelist (88 rules)')
    for i, (f, u, m) in enumerate(zip(fpea, uafx, miss)):
        a.text(i-w/2, f+2500, f'{f/1000:.0f}k', ha='center', va='bottom', fontsize=7, color=c_f)
        if u:
            a.text(i+w/2, u+2500, f'{u:,}\n({m:.1f}%\nmissed)', ha='center', va='bottom',
                   fontsize=6.3, color=c_u, linespacing=1.1)
        else:
            a.text(i+w/2, 2500, 'n/a\n(clang 16)', ha='center', va='bottom', fontsize=6.3, color=c_u)
    a.set_xticks(list(x))
    a.set_xticklabels(VERS, fontsize=7.5)
    a.tick_params(axis='y', labelsize=7.5)
    a.text(-0.02, -0.14, 'missed = share of FPEA entry points absent from the whitelist',
           transform=a.transAxes, fontsize=6, color='gray', ha='left', va='top')
    a.set_ylabel('Driver entry points identified (unit layer)', fontsize=7.5)
    a.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f'{v/1000:.0f}k'))
    a.set_ylim(0, 200000)
    a.legend(loc='upper left', frameon=False, fontsize=6.8)
    a.set_title('(a) Coverage per kernel version', fontsize=8.5, loc='left')


def draw_hit_rate(b, semantic, simple, rand):
    """(b) semantic vs naive hit rate of struct-name + field-index rules."""
    x = range(len(VERS))
    b.plot(list(x), semantic, 'o-', color='#1a202c', lw=1.6, ms=4,
           label='Semantic hit rate\n(index = intended field)')
    b.plot(list(x), simple, 's--', color='#a0aec0', lw=1.1, ms=3.5,
           label='Naive hit rate\n(any function at index)')
    b.scatter([3.18], [0.5], marker='x', color='#c53030', s=35, zorder=5)
    b.annotate('RANDSTRUCT_FULL build (7.1.4):\nsemantic undefined (~0),\nnaive still %.0f%%'
               % rand, (3.18, 0.5), xytext=(-0.1, 12), fontsize=6.3, color='#c53030',
               arrowprops=dict(arrowstyle='-', color='#c53030', lw=0.8, shrinkB=3))
    for i, s in enumerate(semantic):
        b.text(i+(0.12 if i == 3 else 0), s+(3 if i < 3 else 4), f'{s:.1f}%', ha='center',
               fontsize=6.8)
    b.text(3.07, simple[3]-1, f'{simple[3]:.1f}%', ha='left', va='top', fontsize=6.3, color='#718096')
    b.annotate('fop_flags inserted (7.1):\nread 2→3, write 3→4', (3, semantic[3]),
               xytext=(1.75, 62), fontsize=6.3,
               arrowprops=dict(arrowstyle='->', color='gray', lw=0.8))
    b.set_xticks(list(x))
    b.set_xticklabels(VERS, fontsize=7.5)
    b.tick_params(axis='y', labelsize=7.5)
    b.set_ylim(0, 100)   # room for the legend above the curves (single-column layout)
    b.set_ylabel('Rule slots pointing at intended handler (%)', fontsize=7.5)
    b.legend(loc='upper left', frameon=False, fontsize=6.5, bbox_to_anchor=(-0.02, 1.03))
    b.set_title('(b) Validity of struct-name + field-index rules', fontsize=8.5, loc='left')


def main():
    fpea, uafx, miss, semantic, simple, rand = load_data()
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9,
                         'axes.spines.top': False, 'axes.spines.right': False})
    # one column of the two-column manuscript: 3.3 in wide, panels stacked
    fig, (a, b) = plt.subplots(2, 1, figsize=(3.3, 5.6))
    draw_coverage(a, fpea, uafx, miss)
    draw_hit_rate(b, semantic, simple, rand)
    fig.tight_layout(h_pad=2.2)
    for ext in ('pdf', 'png', 'svg'):
        fig.savefig(f'{F}/figures/fig2_version_stability.{ext}', dpi=300, bbox_inches='tight')
    print(fpea, uafx, miss, semantic, simple, rand)


if __name__ == '__main__':
    main()
