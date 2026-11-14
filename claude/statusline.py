#!/usr/bin/env python3
"""Claude Code status line.

Reads the session-context JSON on stdin and prints five rows in three sections:
a bar for the CPU, the context and each usage limit; the numbers that go with
them; and the names of what the session works with. The layout sizes itself to
the terminal. Wired via ~/.claude/settings.json as `python3 ~/.claude/statusline.py`.

  CPU:   ▃▃▃▃▂▂▂▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁  10%   ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ │ AC:  39%     Cost:  $3.63     │ Model: Opus 5.5/High
  Ctx:   ▰▰▰▰▰▰▰▰▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱  191k  ▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱ │ Win: 19%     Turn:  220       │ ID:    1feba53f      claude-00
  5h:    ▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱   2%   ▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱ │ ↻─── 4h46m   𝐏────▕ 111% ▏    │ Dir:   ~/git/personal/bluebird
  7d:    ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▕ 92%  ▏▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱▱▱ │ ├─── 2d21h   ├────▕ 164% ▏    │ Git:   main ↓7 ✚2
  Fable: ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▕ 100% ▏▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰ │ └─── 2d21h   └────▕ 167% ▏    │ K8s:   admin@stable  default

The CPU bar is a chart, a column per core. The Ctx bar spans the model's whole
window. AC is the share of the point where auto-compact fires, Win the share of
the whole window. With auto-compact on, Win can never pass the AC point, so it
only matters when compaction is off (DISABLE_AUTO_COMPACT=1). The Fable row
stays empty until the Fable limit has been fetched. Each limit's row ends in two
trees: ↻ when it resets, and 𝐏 its pace, where it lands at the reset if use
keeps its rate so far (shown once 30 minutes of a 5h window, or 12 hours of a
week, have gone). On the Git row ↑/↓ track the branch's own upstream and ✚
counts changed files; outside a repo, and without a K8s context, a row shows –.

One color per job: mauve labels a value, white is a value, slate teal is the
minor detail that ends a row, lavender draws the colons, slashes and trees, icy
blue draws the dividers, and mint / gold / coral is a value with a limit: mint
under 50%, gold under 80%, and from 80% bold coral, boxed by coral edges with a
line above and below. Ctx's token count takes AC's color. The bars fill in
quieter tones with the same steps: steel blue, soft violet, orchid. The Model
row is bold, as the right side's lead.

The session's short name (`claude-80`) is what other sessions message it by;
the 8-character ID prefix is what create-issue labels its issues with.

Everything is read in collect() and drawn in render(), which takes the readings
and returns the text, so the layout can be tested anywhere. Only the standard
library is used, and it runs on macOS's own Python 3.9.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

HOME = os.path.expanduser("~")
CACHE = os.path.join(HOME, ".claude", "cache")

# --- Palette ---
E = "\033"
R = E + "[0m"
LAB = E + "[38;5;139m"    # mauve: labels
DIV = E + "[38;5;153m"    # icy pale blue: the dividers
VAL = E + "[97m"          # white: values
VALB = E + "[1;97m"       # bold white: the model, the right side's lead value
DET = E + "[38;5;66m"     # slate teal: the minor detail that ends a row
DOT = E + "[38;5;103m"    # lavender: colons and the trees
SLASH = E + "[1;38;5;103m"  # bold lavender: the slashes in names and paths
OK, WARN, BAD = E + "[38;5;151m", E + "[38;5;222m", E + "[38;5;210m"  # mint, gold, coral
# The bars fill in quieter tones from the same palette, so a long bar doesn't
# shout over the numbers beside it: steel blue, soft violet, orchid.
BAR_OK, BAR_WARN, BAR_BAD = E + "[38;5;110m", E + "[38;5;140m", E + "[38;5;175m"
CRIT = E + "[1;38;5;210m"  # bold coral: a value past its limit
BOX = E + "[4;53m"         # underline and overline: with coral edges, a box around it
EMPTY = E + "[38;5;237m"
SPARK = "▁▂▃▄▅▆▇█"


def rgb(r, g, b):
    return "%s[38;2;%d;%d;%dm" % (E, r, g, b)


RAINBOW = [rgb(235, 95, 87), rgb(245, 139, 87), rgb(250, 195, 95), rgb(145, 200, 130),
           rgb(130, 170, 220), rgb(155, 130, 200), rgb(200, 130, 180)]
ULTRA = rgb(175, 135, 255)  # xhigh's base purple, the CLI's autoAccept
EFFORT = {"low": rgb(255, 193, 7), "medium": rgb(78, 186, 101), "high": rgb(177, 185, 249)}


# --- Styled text ---
# Every piece carries its text and color together, so what is measured is what
# is printed. A part with a style prints as style + text + reset.
class T:
    __slots__ = ("parts",)

    def __init__(self, parts=None):
        self.parts = parts or []

    def __add__(self, other):
        return T(self.parts + other.parts)

    def __len__(self):
        return len(self.plain)

    @property
    def plain(self):
        return "".join(t for t, _ in self.parts)

    def ansi(self):
        return "".join(s + t + R if s else t for t, s in self.parts)


def P(text):
    return T([(text, "")])


def S(style, text):
    return T([(text, style)])


def sp(n):
    return " " * n if n > 0 else ""


def boxed(text):
    """TEXT in bold coral inside a box: coral edges, a line above and below.
    The edges draw at the inner side of their cells, so the lines run only
    between them and meet the edges instead of overhanging. Each part restates
    BOX, since every reset clears it."""
    return S(BAD, "▕") + S(CRIT + BOX, " " + text + " ") + S(BAD, "▏")


def val(v, w=50, c=80):
    """A percentage in its limit color -> (styled, text, color, past_limit)."""
    t = "%d%%" % v
    if v >= c:
        return boxed(t), t, CRIT, True
    if v >= w:
        return S(WARN, t), t, WARN, False
    return S(OK, t), t, OK, False


def slashed(text, color):
    """TEXT in COLOR with every / in bold lavender."""
    segs = text.split("/")
    out = S(color, segs[0])
    for s in segs[1:]:
        out = out + S(SLASH, "/") + S(color, s)
    return out


def sevc(v, w=50, c=80):
    return BAR_BAD if v >= c else BAR_WARN if v >= w else BAR_OK


# --- Bars ---
def bar(num, den, col, bw):
    """Cells for a bar in whole segments: (glyph, color) each."""
    if den <= 0:
        den = 1
    fill = min((num * bw + den // 2) // den, bw)
    # A sliver of use still shows one segment.
    if num > 0 and fill == 0:
        fill = 1
    return [("▰", col) if i < fill else ("▱", EMPTY) for i in range(bw)]


def core_chart(cores, bw):
    """With per-core numbers, the CPU's bar becomes a chart: each core a column
    that rises with its load, stretched across the bar's width. When the width
    isn't a multiple of the core count, some cores get one more column."""
    n = len(cores)
    cells = []
    for j in range(bw):
        p = cores[j * n // bw]
        cells.append((SPARK[7 if p >= 100 else p * 8 // 100], sevc(p)))
    return cells


def finish_bar(cells, t, col, past):
    """The cells with the number in the middle. Every bar cuts the same slot, a
    box's width, and centers the number in it (an odd space goes after), so 9%
    and 100% take the same room and a box is always the same size."""
    bw = len(cells)
    w = max(4, len(t))
    span = w + 4
    lp, rp = sp((w - len(t)) // 2), sp((w - len(t) + 1) // 2)
    if past:
        slot = boxed(lp + t + rp)
    else:
        slot = P("  " + lp) + S(col, t) + P(rp + "  ")
    st = max(0, (bw - span) // 2)
    out = T()
    for i, (ch, fg) in enumerate(cells):
        if i < st or i >= st + span:
            out = out + S(fg, ch)
        elif i == st:
            out = out + slot
    # Then an icy blue divider, as between the values and the right side.
    return out + P(" ") + S(DIV, "│") + P(" ")


def row_label(name):
    return S(LAB, name) + S(DOT, ":") + P(sp(6 - len(name)))


def cell(t, col, past, width, col_boxed, last=False):
    """One value in a grid column. When either value in a column is boxed, the
    other gets blank cells where the box's edges go, so the numbers line up."""
    pad = "" if last else sp(width - len(t))
    if past:
        return boxed(t + pad)
    if col_boxed:
        out = P("  ") + S(col, t) + P(pad)
        return out if last else out + P("  ")
    return S(col, t) + P(pad)


def graded_cell(num, w, c, text):
    """A value in the color NUM earns, as (styled, text, color, past_limit)."""
    if num >= c:
        return None, text, CRIT, True
    return None, text, WARN if num >= w else OK, False


def build_left(st, bw, with_third=True):
    """The left rows: 0 Ctx, 1 5h, 2 7d, 3 Fable, and 4 the machine (printed
    above them). Each row's number sits in the middle of its bar. with_third
    False leaves out the paces, for a narrow terminal."""
    rows = [T() for _ in range(5)]
    _, _, ack, acx = val(st.ac_pct)
    rows[0] = row_label("Ctx") + finish_bar(bar(st.ctx_tok, st.win, sevc(st.ac_pct), bw),
                                            "%dk" % (st.ctx_tok // 1000), ack, acx)
    for i, name, pct in ((1, "5h", st.five_pct), (2, "7d", st.seven_pct), (3, "Fable", st.fable_pct)):
        if pct is None:
            continue
        _, t, k, x = val(pct)
        rows[i] = row_label(name) + finish_bar(bar(pct, 100, sevc(pct), bw), t, k, x)
    _, t, k, x = val(st.cpu_pct)
    cells = core_chart(st.cores, bw) if st.cores else bar(st.cpu_pct, 100, sevc(st.cpu_pct), bw)
    rows[4] = row_label("CPU") + finish_bar(cells, t, k, x)

    # AC and Win, the two shares of the context, stack as a column of their own.
    a, n = val(st.ac_pct), val(st.win_pct)
    w, bx = max(len(a[1]), len(n[1])), a[3] or n[3]
    for i, lab, v in ((4, "AC", a), (0, "Win", n)):
        rows[i] = rows[i] + S(LAB, lab) + S(DOT, ":") + P(sp(3 - len(lab)) + ("" if bx else " ")) + cell(v[1], v[2], v[3], w, bx)

    # The reset times hang off ↻ tree-style, one on each limit's row. The
    # branches reach the column AC and Win's numbers start in (one further
    # when that column is boxed), so the times line up under them.
    dash = "─" * (4 if bx else 3)
    # ↻ stands in for the "Resets" label, so it is mauve like a label, and bold.
    rows[1] = rows[1] + S(E + "[1;38;5;139m", "↻") + S(DOT, dash) + P(" ") + S(VAL, st.five_r)
    if st.fable_pct is not None:
        rows[2] = rows[2] + S(DOT, "├" + dash) + P(" ") + S(VAL, st.seven_r)
        rows[3] = rows[3] + S(DOT, "└" + dash) + P(" ") + S(VAL, st.fable_r)
    else:
        rows[2] = rows[2] + S(DOT, "└" + dash) + P(" ") + S(VAL, st.seven_r)
        # No Fable bar: the row keeps the divider, so it runs unbroken.
        rows[3] = P(sp(7 + bw + 1)) + S(DIV, "│") + P(" ")

    # Cost and Turn head the next column, and each limit's pace hangs off 𝐏
    # below them tree-style, beside its reset time. The column starts where the
    # longest row before it ends: the reset times, or on a narrow terminal
    # (with_third False, the paces left out) AC and Win. Labels pad to the
    # longer one, the branches reach the same column, and a boxed value's edge
    # stands in for the space before it.
    labeled = {4: ("Cost", graded_cell(int(st.cost.split(".")[0]), 50, 100, "$" + st.cost)),
               0: ("Turn", graded_cell(st.turns, 150, 300, str(st.turns)))}
    paces = {}
    if with_third:
        limits = [(1, st.five_pace), (2, st.seven_pace)] + ([(3, st.fable_pace)] if st.fable_pct is not None else [])
        for n, (i, p) in enumerate(limits):
            glyph = S(E + "[1;38;5;139m", "𝐏") if n == 0 else S(DOT, "└" if n == len(limits) - 1 else "├")
            paces[i] = (glyph, val(p) if p is not None else (None, "–", DET, False))
    col = list(labeled.values()) + list(paces.values())
    start = max(len(rows[i]) for i in list(labeled) + list(paces))
    lw3 = max(len(lab) for lab, _ in labeled.values())
    vw3 = max(len(v[1]) for _, v in col)
    bx3 = any(v[3] for _, v in col)
    gap = "" if bx3 else " "
    for i, (lab, v) in labeled.items():
        rows[i] = (rows[i] + P(sp(start - len(rows[i]) + 3)) + S(LAB, lab) + S(DOT, ":")
                   + P(sp(lw3 - len(lab)) + gap) + cell(v[1], v[2], v[3], vw3, bx3, last=True))
    for i, (glyph, v) in paces.items():
        rows[i] = (rows[i] + P(sp(start - len(rows[i]) + 3)) + glyph + S(DOT, "─" * lw3)
                   + P(gap) + cell(v[1], v[2], v[3], vw3, bx3, last=True))
    return rows


# --- Right rows: a mauve label, a bright part, then a slate teal detail ---
def short_dir(p):
    """Long paths keep the first two folders and the last one: ~/.claude/tmp/…/scratchpad."""
    if len(p) <= 32:
        return p
    parts = p.split("/")
    if parts and parts[-1] == "":
        parts.pop()
    if len(parts) <= 4:
        return p
    return "%s/%s/%s/…/%s" % (parts[0], parts[1], parts[2], parts[-1])


def effort_colored(w, lvl, now, bold=False):
    """Effort takes the colors of Claude Code's /effort picker. Its animations
    tick every 100 ms; a status line only redraws on events and the refresh
    timer, so xhigh's highlight steps a letter per redraw. Max's rainbow holds
    still, spread end to end across the word, because stepping it popped
    instead of flowing."""
    n = len(w)
    if lvl in EFFORT:
        return S((E + "[1m" if bold else "") + EFFORT[lvl], w)
    if lvl == "xhigh":
        p = now % (n + 4) - 2
        out = T()
        for i, ch in enumerate(w):
            if i == p:
                out = out + S(E + "[1m" + rgb(208, 180, 255), ch)
            elif abs(i - p) == 1:
                out = out + S(E + "[1m" + ULTRA, ch)
            else:
                out = out + S(ULTRA, ch)
        return out
    if lvl == "max":
        out = T()
        for i, ch in enumerate(w):
            out = out + S(E + "[1m" + RAINBOW[i * 6 // (n - 1) if n > 1 else 0], ch)
        return out
    return S(VALB if bold else VAL, w)


def build_right(st, now):
    """The right rows, top to bottom: Model, ID, Dir, Git, K8s. -> bright parts,
    details and labels by row, and the row whose bright part is the folder's
    path (it may shorten). A row with nothing to show (outside a repo, no K8s
    context) shows a teal dash."""
    # The model is the right side's lead value, so its whole row is bold, its
    # label included (in render); the other rows stay plain.
    effort = S(VALB, st.model) + S(SLASH, "/") + effort_colored(st.effort, st.lvl, now, bold=True)
    model = ("Model", effort, T())
    ident = ("ID", S(VAL, st.sid8), S(DET, st.sname) if st.sname else T())
    kube = ("K8s", S(VAL, st.kube) if st.kube else S(DET, "–"), S(DET, st.ns) if st.ns else T())
    if st.in_git:
        git = slashed(st.branch, VAL)
        if st.ahead > 0:
            git = git + P(" ") + S(OK, "↑%d" % st.ahead)
        if st.behind > 0:
            git = git + P(" ") + S(BAD, "↓%d" % st.behind)
        git = git + P(" ") + (S(WARN, "✚%d" % st.dirty) if st.dirty > 0 else S(OK, "✓"))
    else:
        git = S(DET, "–")
    folder = ("Dir", slashed(st.sdir, VAL), T())
    rows, entries = [4, 0, 1, 2, 3], [model, ident, folder, ("Git", git, T()), kube]
    dir_row = 1
    br, gr, rlab = [T() for _ in range(5)], [T() for _ in range(5)], [""] * 5
    for i, (lab, b, g) in zip(rows, entries):
        rlab[i], br[i], gr[i] = lab, b, g
    return br, gr, rlab, dir_row


def render(st, cols, now):
    # The rows in the order they print: the machine row on top.
    order = [4, 0, 1, 2, 3]
    br, gr, rlab, dir_row = build_right(st, now)

    # The details start in one column: pad each bright part to the widest one
    # that has a detail after it.
    mw = max([len(br[i]) for i in order if len(gr[i])] or [0])

    # --- Width ---
    # Claude Code passes the terminal's width and keeps a few columns for its own
    # padding. The right side keeps its natural width; the bars take what is
    # left, up to four characters per core, and the values column keeps at most 3
    # spare. On a narrower terminal the bars win over the teal details: they hold
    # at two characters per core while the details shorten, then drop. Then the
    # bars go to one per core, then the third column of values drops, and last
    # the whole right side.
    ncpu = st.ncpu
    w_avail = (cols if cols > 0 else 145) - 5
    # The third column of values goes before the right side does: when the
    # right side can't fit beside it, the layout is worked out again without it.
    for with_third in (True, False):
        left = build_left(st, ncpu, with_third)
        # A left row is its label (7), the bar, then the divider with a space on
        # each side (3); a right row starts with its label (7).
        bmin = max([0] + [len(left[i]) - ncpu - 10 for i in order])
        cb, cf = 0, 0
        for i in order:
            # The folder can shorten from the front, so it asks for 16 at most.
            cb = max(cb, min(len(br[i]), 16) if i == dir_row else len(br[i]))
            cf = max(cf, mw + 2 + len(gr[i]) if len(gr[i]) else len(br[i]))
        cb, cf = cb + 7, cf + 7
        # The left side with the bars at one and two characters per core.
        l1, l2 = ncpu + 10 + bmin, 2 * ncpu + 10 + bmin
        pmax, c = 4, 0
        if l2 + 3 + cf <= w_avail:
            show, c = "full", cf
        elif l2 + 3 + 7 + mw + 2 + 16 <= w_avail:
            # The details get whatever the right side has left; a long one ends in ….
            show, pmax = "full", 2
            c = w_avail - l2 - 3
            room = c - 7 - mw - 2
            for i in order:
                if len(gr[i]) > room:
                    gr[i] = slashed(gr[i].plain[:room - 1] + "…", DET)
        elif l2 + 3 + cb <= w_avail:
            show, c = "bright", cb
        elif l1 + 3 + cb <= w_avail:
            show, pmax, c = "bright", 2, cb
        else:
            show = "left"
        if show != "left":
            break
    # A folder longer than the right side's room keeps the whole folders at its
    # end that fit (…/personal/bluebird), or the last one cut short.
    if show != "left" and len(br[dir_row]) > c - 7:
        room, tail = c - 7, br[dir_row].plain.split("/")[-1]
        for seg in reversed(br[dir_row].plain.split("/")[1:-1]):
            if len("…/" + seg + "/" + tail) > room:
                break
            tail = seg + "/" + tail
        t = "…/" + tail
        br[dir_row] = slashed(t if len(t) <= room else "…" + tail[-(room - 1):], VAL)
    avail = w_avail if show == "left" else w_avail - 3 - c
    per = pmax
    while per > 1 and per * ncpu + 10 + bmin > avail:
        per -= 1
    # The bars then take every spare column, up to four per core, so no width
    # leaves a gap at the end of the line.
    bw = max(per * ncpu, min(avail - 10 - bmin, pmax * ncpu))
    left = build_left(st, bw, with_third)
    # The values column pads out to the divider by 3 spare columns at most; any
    # other leftover goes at the end of the line, where empty space doesn't show.
    lw = 0 if show == "left" else min(avail, bw + 10 + bmin + 3)
    lw = max([lw] + [len(left[i]) for i in order])

    out = []
    for i in order:
        if show == "left":
            out.append(left[i].ansi())
            continue
        line = left[i].ansi() + sp(lw - len(left[i]))
        bold = E + "[1m" if rlab[i] == "Model" else ""
        line += DIV + " │ " + R + bold + LAB + rlab[i] + R + bold + DOT + ":" + R + sp(6 - len(rlab[i])) + br[i].ansi()
        if show == "full" and len(gr[i]):
            line += sp(mw - len(br[i]) + 2) + gr[i].ansi()
        out.append(line)
    return "\n".join(out)


# --- Reading the session and the machine ---
def jget(d, *path, default=None):
    """A value from nested JSON, falling back like jq's // on null or false."""
    for k in path:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return default if d is None or d is False else d


def jround(x):
    """jq's round: halves away from zero."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return 0
    return int(x + 0.5) if x >= 0 else -int(-x + 0.5)


def num(x, default=0):
    try:
        return int(x)
    except (TypeError, ValueError):
        try:
            return int(float(x))
        except (TypeError, ValueError):
            return default


def run(args, cwd=None):
    """stdout of a command, or None when it fails or is missing."""
    try:
        p = subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.decode("utf-8", "replace") if p.returncode == 0 else None


def age(path, now):
    try:
        return now - int(os.stat(path).st_mtime)
    except OSError:
        return 999999


def write_atomic(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d" % (path, os.getpid())
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a"):
        os.utime(path, None)


def spawn(flag):
    """Run this script again in the background with FLAG, detached, so a slow
    reading never holds up the status line."""
    try:
        subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__), flag],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True)
    except OSError:
        pass


def fmt_reset(ts, now):
    if ts <= 0:
        return "-"
    d = ts - now
    if d <= 0:
        return "now"
    if d >= 172800:
        return "%dd%dh" % (d // 86400, d % 86400 // 3600)
    if d >= 3600:
        return "%dh%dm" % (d // 3600, d % 3600 // 60)
    return "%dm" % (d // 60)


def pace(pct, reset, window, now, early=1800):
    """Where a usage limit lands at its reset if use keeps its rate so far:
    PCT used with the share of WINDOW (seconds) gone that RESET implies. None
    without a reset, or before EARLY seconds of the window have gone, when a
    projection is mostly noise."""
    gone = window - (reset - now)
    if reset <= 0 or gone < early:
        return None
    return int(pct * window / gone + 0.5)


def to_tokens(v, bare=False):
    """"200000" | "200k" | "1M" -> tokens if 100K..1M, else None. bare also reads
    a bare 100..1000 as thousands, as /autocompact and the setting do."""
    n, m = str(v).lower(), 1
    if n.endswith("k"):
        n, m = n[:-1], 1000
    elif n.endswith("m"):
        n, m = n[:-1], 1000000
    if not re.fullmatch(r"[0-9]+(\.[0-9]+)?", n):
        return None
    t = float(n) * m
    if bare and m == 1 and 100 <= t <= 1000:
        t *= 1000
    return int(t) if 100000 <= t <= 1000000 else None


def jq_text(v):
    """A JSON value as jq -r prints it."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return v
    return json.dumps(v)


def ac_threshold(win, model_id, env, settings):
    """The payload says how big the window is but not where auto-compact fires,
    so that is rebuilt from the CLI's own formula (checked against the 2.1.312
    binary):
      window    = context_window_size, lowered by an auto-compact window override
                  (CLAUDE_CODE_AUTO_COMPACT_WINDOW > modelSettings.<id> > autoCompactWindow)
      effective = window - 20000            # reserved for the model's output
      threshold = effective - 13000         # reserved for the compaction summary
      with CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=p: threshold = min(effective*p/100, threshold)
    Those env vars reach this script because settings.json `env` is applied to
    the CLI process and inherited here. A one-off `claude --autocompact N` is
    invisible."""
    acwin = win
    ov = to_tokens(env.get("CLAUDE_CODE_AUTO_COMPACT_WINDOW", ""))
    if ov is None:
        v = jget(settings, "modelSettings", model_id, "autoCompactWindow")
        if v is None:
            v = jget(settings, "autoCompactWindow")
        if v is not None:
            ov = to_tokens(jq_text(v), bare=True)
    if ov is not None and ov < acwin:
        acwin = ov
    e = acwin - 20000
    t = e - 13000
    m = re.match(r"\s*[-+]?[0-9]*\.?[0-9]+", env.get("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", ""))
    p = float(m.group()) if m else 0
    if 0 < p <= 100:
        t = min(int(e * p / 100), t)
    return t


def merge_limits(old_text, five, seven):
    """Each session's payload only refreshes its limits when that session gets an
    API reply, so an idle session would show stale numbers. The limits are
    account-wide, so every session pools what it has seen in one file and shows
    the newest. A later reset time is a newer window, and within one window usage
    only climbs. -> (merged JSON text, five, seven) or None when the file is
    unreadable."""
    def newer(a, b):
        ar, br_ = a.get("reset") or 0, b.get("reset") or 0
        if br_ > ar or (br_ == ar and (b.get("pct") or 0) > (a.get("pct") or 0)):
            return b
        return a

    try:
        old = json.loads(old_text)
        f = newer(old.get("five") or {}, {"pct": five[0], "reset": five[1]})
        s = newer(old.get("seven") or {}, {"pct": seven[0], "reset": seven[1]})
    except (ValueError, AttributeError, TypeError):
        return None
    merged = {"five": f, "seven": s}
    return (json.dumps(merged, separators=(",", ":"), ensure_ascii=False),
            (num(f.get("pct")), num(f.get("reset"))), (num(s.get("pct")), num(s.get("reset"))))


def count_turns(data, prev):
    """Each prompt you send gets its own promptId in the transcript. -> (new
    prompts in DATA, the last promptId seen)."""
    n, seen, last = 0, set(), ""
    for m in re.findall(rb'"promptId":"[^"\n]*"', data):
        m = m.decode("utf-8", "replace")
        if m != prev and m not in seen:
            n += 1
        if m != prev:
            seen.add(m)
        last = m
    return n, last or prev


def read_turns(tpath, sid):
    """A long session's transcript runs to tens of MB, so the count is kept per
    session and only the bytes added since the last run are read."""
    if not tpath or not os.path.isfile(tpath):
        return 0
    tc = os.path.join(CACHE, "turns-" + sid)
    size = os.path.getsize(tpath)
    off, cnt, last = 0, 0, ""
    try:
        with open(tc) as f:
            parts = f.read().split()
        off, cnt = num(parts[0]), num(parts[1])
        last = parts[2] if len(parts) > 2 else ""
    except (OSError, IndexError):
        pass
    if size < off:
        off, cnt, last = 0, 0, ""
    if size > off:
        with open(tpath, "rb") as f:
            f.seek(off)
            add, last = count_turns(f.read(), last)
        cnt += add
        write_atomic(tc, "%d %d %s\n" % (size, cnt, last))
    return cnt


def cpu_cores():
    """Per-core usage straight from the kernel's tick counters
    (host_processor_info), as the change since the previous reading, about 10 s
    earlier. macOS has no command for it, so it's read through ctypes."""
    import ctypes
    import ctypes.util
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    n, cnt = ctypes.c_uint(), ctypes.c_uint()
    info = ctypes.POINTER(ctypes.c_int)()
    libc.mach_host_self.restype = ctypes.c_uint
    if libc.host_processor_info(libc.mach_host_self(), 2, ctypes.byref(n), ctypes.byref(info), ctypes.byref(cnt)) != 0:
        return []
    cur = [[info[i * 4 + j] & 0xFFFFFFFF for j in range(4)] for i in range(n.value)]  # user, system, idle, nice
    path = os.path.join(CACHE, "cpu-ticks")
    try:
        with open(path) as f:
            prev = [[int(x) for x in line.split()] for line in f]
    except (OSError, ValueError):
        prev = []
    if len(prev) != len(cur):
        prev = [[0, 0, 0, 0] for _ in cur]
    out = []
    for a, b in zip(cur, prev):
        d = [(x - y) % 2**32 for x, y in zip(a, b)]
        tot = sum(d)
        out.append(round(100 * (tot - d[2]) / tot) if tot else 0)
    write_atomic(path, "\n".join(" ".join(map(str, c)) for c in cur))
    return out


def read_machine(now, ncpu):
    """One reading of the CPU is shared by every session for 10 s, so they all
    show the same numbers. The first session past that takes the next one.
    -> overall percent, per-core percents."""
    path = os.path.join(CACHE, "machine-v5")
    if age(path, now) < 10:
        try:
            with open(path) as f:
                p = f.readline().rstrip("\n").split("\t") + [""]
            return num(p[0]), [int(x) for x in p[1].split()]
        except (OSError, ValueError):
            pass
    try:
        cores = cpu_cores()
    except (OSError, AttributeError, ValueError):
        cores = []
    if cores:
        cpu = int(sum(cores) / len(cores) + 0.5)
    else:
        # Without the kernel counters: ps reports each process's recent share of one core.
        out = run(["ps", "-A", "-o", "%cpu="]) or ""
        cpu = min(100, int(sum(float(x) for x in out.split() if x) / ncpu + 0.5))
    write_atomic(path, "%d\t%s\n" % (cpu, " ".join(map(str, cores))))
    return cpu, cores


def read_fable(now):
    """The Fable model-scoped weekly limit isn't in the payload, so it's pulled
    from the OAuth usage endpoint (the same source as /usage) and cached; a
    background refresh at most every 5 min keeps the render fast and offline-safe.
    -> (percent or None, reset time)."""
    cache, stamp = os.path.join(CACHE, "fable-limit.json"), os.path.join(CACHE, "fable-limit.stamp")
    pct, reset = None, 0
    try:
        with open(cache) as f:
            d = json.load(f)
        p, r = d.get("percent"), d.get("resets_at")
        if r is None or isinstance(r, str):
            if isinstance(p, int) and not isinstance(p, bool) and p >= 0:
                pct = p
            if r:
                r = re.sub(r"\+00:00$", "Z", re.sub(r"\.[0-9]+", "", r, count=1))
                try:
                    import calendar
                    reset = calendar.timegm(time.strptime(r, "%Y-%m-%dT%H:%M:%SZ"))
                except ValueError:
                    reset = 0
    except (OSError, ValueError, AttributeError):
        pass
    # The cache's age is the data's: it's only rewritten on a successful fetch.
    # Past 3 h (an expired token, a long time offline) it's hidden rather than
    # show a number that may be days out of date.
    if age(cache, now) >= 10800:
        pct = None
    # The stamp paces fetch attempts, touched up front whether or not they
    # succeed, so a failing fetch retries every 5 min instead of on every render.
    if age(stamp, now) >= 300:
        try:
            touch(stamp)
        except OSError:
            pass
        spawn("--fetch-fable")
    return pct, reset


def refresh_fable():
    tok = None
    out = run(["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"])
    for src in (out, None):
        try:
            if src is None:
                with open(os.path.join(HOME, ".claude", ".credentials.json")) as f:
                    src = f.read()
            tok = jget(json.loads(src), "claudeAiOauth", "accessToken")
        except (OSError, ValueError, TypeError):
            tok = None
        if tok:
            break
    if not tok:
        return
    import urllib.request
    req = urllib.request.Request("https://api.anthropic.com/api/oauth/usage", headers={
        "Authorization": "Bearer " + tok, "anthropic-beta": "oauth-2025-04-20", "User-Agent": "statusline"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
    except (OSError, ValueError):
        return
    for lim in data.get("limits") or []:
        if lim.get("kind") == "weekly_scoped" and re.search("fable", jget(lim, "scope", "model", "display_name", default="") or "", re.I):
            write_atomic(os.path.join(CACHE, "fable-limit.json"), json.dumps(lim, separators=(",", ":")))
            return


def collect(payload, env=os.environ):
    st = SimpleNamespace()
    st.model = str(jget(payload, "model", "display_name", default="?"))
    effort = str(jget(payload, "effort", "level", default="?"))
    st.win_pct = jround(jget(payload, "context_window", "used_percentage", default=0))
    st.ctx_tok = num(jget(payload, "context_window", "total_input_tokens", default=0))
    five = (jround(jget(payload, "rate_limits", "five_hour", "used_percentage", default=0)),
            num(jget(payload, "rate_limits", "five_hour", "resets_at", default=0)))
    seven = (jround(jget(payload, "rate_limits", "seven_day", "used_percentage", default=0)),
             num(jget(payload, "rate_limits", "seven_day", "resets_at", default=0)))
    cost = jget(payload, "cost", "total_cost_usd", default=0)
    sid = str(jget(payload, "session_id", default="?"))
    st.win = num(jget(payload, "context_window", "context_window_size", default=0))
    mid = str(jget(payload, "model", "id", default=""))
    cwd = str(jget(payload, "workspace", "current_dir", default=None) or jget(payload, "cwd", default=""))
    tpath = str(jget(payload, "transcript_path", default=""))
    d = cwd[len(HOME):] if cwd.startswith(HOME) else None
    st.dir = "~" + d if d is not None else cwd

    # The short session name is not in the payload: Claude Code's messaging
    # registry keeps it per process in ~/.claude/sessions/<pid>.json, keyed by
    # the same session id. A session started without messaging has no entry.
    st.sname = ""
    for f in sorted(glob.glob(os.path.join(HOME, ".claude", "sessions", "*.json"))):
        try:
            with open(f) as fh:
                s = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(s, dict) and s.get("sessionId") == sid and s.get("name") not in (None, False):
            st.sname = str(s["name"])
            break
    st.lvl = effort.lower()
    st.effort = effort[:1].upper() + effort[1:]

    # One git call gives the branch, ahead/behind and changed files. A plain
    # status takes the index lock to refresh it, and with the status line
    # re-running on a timer that lock can collide with an agent's own git command
    # in the same repo ("index.lock exists"), so it runs without optional locks.
    st.in_git, st.branch, st.ahead, st.behind, st.dirty = False, "", 0, 0, 0
    gs = run(["git", "-C", cwd, "--no-optional-locks", "status", "--porcelain=v2", "--branch"])
    if gs is not None:
        st.in_git = True
        for line in gs.rstrip("\n").split("\n"):
            f = line.split()
            if line.startswith("# branch.head ") and len(f) > 2:
                st.branch = "detached" if f[2] == "(detached)" else f[2]
            elif line.startswith("# branch.ab ") and len(f) > 3:
                st.ahead, st.behind = num(f[2][1:]), num(f[3][1:])
            elif not line.startswith("# "):
                st.dirty += 1

    # K8s context and namespace (the namespace needs a second query, only when a
    # context is set).
    st.kube, st.ns = "", ""
    if shutil.which("kubectl"):
        c = (run(["kubectl", "config", "current-context"]) or "").rstrip("\n")
        if c:
            st.kube = c
            st.ns = (run(["kubectl", "config", "view", "--minify", "-o", "jsonpath={..namespace}"]) or "").rstrip("\n") or "default"

    try:
        st.cost = "%.2f" % float(cost)
    except (TypeError, ValueError):
        st.cost = "0.00"
    if st.win <= 0:
        st.win = 200000
    try:
        with open(os.path.join(HOME, ".claude", "settings.json")) as f:
            settings = json.load(f)
    except (OSError, ValueError):
        settings = {}
    ac_thr = ac_threshold(st.win, mid, env, settings)
    st.ac_pct = int(st.ctx_tok / ac_thr * 100 + 0.5) if ac_thr > 0 else 0

    now = int(time.time())
    st.now = now
    lc = os.path.join(CACHE, "usage-limits.json")
    try:
        with open(lc) as f:
            old = f.read()
    except OSError:
        old = ""
    m = merge_limits(old or "{}", five, seven)
    if m:
        text, five, seven = m
        if text != (old or "{}"):
            write_atomic(lc, text)
    # A window whose reset has passed starts again from zero.
    if 0 < five[1] <= now:
        five = (0, 0)
    if 0 < seven[1] <= now:
        seven = (0, 0)
    st.five_pct, st.seven_pct = five[0], seven[0]
    st.five_r, st.seven_r = fmt_reset(five[1], now), fmt_reset(seven[1], now)
    st.five_pace = pace(five[0], five[1], 5 * 3600, now)
    st.seven_pace = pace(seven[0], seven[1], 7 * 86400, now, early=12 * 3600)

    st.fable_pct, fable_reset = read_fable(now)
    st.fable_r = fmt_reset(fable_reset, now)
    st.fable_pace = pace(st.fable_pct, fable_reset, 7 * 86400, now, early=12 * 3600) if st.fable_pct is not None else None

    st.ncpu = os.cpu_count() or 1
    st.cpu_pct, st.cores = read_machine(now, st.ncpu)
    st.turns = read_turns(tpath, sid)

    st.sdir = short_dir(st.dir)
    # Branch names stop at 20 characters so one long name can't push the grey column away.
    if len(st.branch) > 20:
        st.branch = st.branch[:19] + "…"
    st.sid8 = sid[:8]

    return st


def main():
    if sys.argv[1:] == ["--fetch-fable"]:
        refresh_fable()
        return
    try:
        try:
            payload = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        except ValueError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        st = collect(payload)
        out = render(st, num(os.environ.get("COLUMNS"), 145), st.now)
    except Exception as e:  # a broken status line should still say why
        out = "statusline.py: %s: %s" % (type(e).__name__, e)
    sys.stdout.buffer.write(out.encode("utf-8"))


if __name__ == "__main__":
    main()
