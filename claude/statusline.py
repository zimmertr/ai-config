#!/usr/bin/env python3
"""Claude Code status line.

Reads the session-context JSON on stdin and prints five rows: the machine on
top, then a bar for context and each usage limit on the left, and what the
session is working with on the right. The layout sizes itself to the terminal.
Wired via ~/.claude/settings.json as `python3 ~/.claude/statusline.py`.

  CPU:   ▕ ▃▃▃▃▂▂▂▁▁▁▁▁▁▁▁▁▁▁  10%   ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁ ▏ Mem: 32% · GPU: 0%  · Temp:   45°    │ Net:   ↓5.7 KB/s ↑4.5 KB/s
  Ctx:   ▕ ▰▰▰▰▰▰▰▰▰▱▱▱▱▱▱▱▱▱  191k  ▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱ ▏ AC:  39% · Win: 19%                  │ Model: Opus 5.5/High
  5h:    ▕ ▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱   2%   ▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱ ▏ Resets: 4h46m         Cache:▕ 100% ▏ │ Git:   main ↓7 ✚2    ~/git/personal/bluebird
  7d:    ▕ ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▕ 92%  ▏▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱▱▱ ▏   ├──── 2d21h         Cost:   $3.63  │ K8s:   admin@stable  default
  Fable: ▕ ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▕ 100% ▏▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰ ▏   └──── 2d21h         Turn:   220    │ ID:    1feba53f      claude-00

The Ctx bar spans the model's whole window. AC is the share of the point where
auto-compact fires, Win the share of the whole window. With auto-compact on,
Win can never pass the AC point, so it only matters when compaction is off
(DISABLE_AUTO_COMPACT=1). The Fable row is hidden until the Fable limit has been
fetched. The Git row reads Dir outside a repo; ↑/↓ track the branch's own
upstream, ✚ counts changed files. Cache is how much of the prompt cache's life
has gone since the last message.

One color per job: mauve labels a value, white is a value, slate teal is the
minor detail that ends a row, lavender draws the dots, colons, slashes, arrows
and the resets tree, icy blue draws the dividers, and mint / gold / coral is a
value with a limit: mint under 50%, gold under 80%, and from 80% bold coral,
boxed by coral edges with a line above and below. Ctx's token count takes AC's
color. The bars fill in quieter tones with the same steps: steel blue, soft
violet, orchid.

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
DET = E + "[38;5;66m"     # slate teal: the minor detail that ends a row
DOT = E + "[38;5;103m"    # lavender: dots, colons, arrows and the resets tree
SLASH = E + "[1;38;5;103m"  # bold lavender: the slashes in names and paths
DIM = E + "[38;5;243m"    # dim grey: the bar's edges
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
    # Each part restates BOX, since every reset clears it.
    return S(BAD + BOX, "▕ ") + S(CRIT + BOX, text) + S(BAD + BOX, " ▏")


def val(v, w=50, c=80):
    """A percentage in its limit color -> (styled, text, color, past_limit)."""
    t = "%d%%" % v
    if v >= c:
        return boxed(t), t, CRIT, True
    if v >= w:
        return S(WARN, t), t, WARN, False
    return S(OK, t), t, OK, False


def graded(num, w, c, text, nobox=False):
    """TEXT in the color NUM earns. nobox keeps a value past its limit plain
    coral, for a value whose width must hold still because the details after it
    line up."""
    if num >= c:
        return S(CRIT, text) if nobox else boxed(text)
    if num >= w:
        return S(WARN, text)
    return S(OK, text)


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
        slot = S(BAD + BOX, "▕ ") + S(CRIT + BOX, lp + t + rp) + S(BAD + BOX, " ▏")
    else:
        slot = P("  " + lp) + S(col, t) + P(rp + "  ")
    st = max(0, (bw - span) // 2)
    # A space inside each edge keeps the bar off its frame.
    out = S(DIM, "▕") + P(" ")
    for i, (ch, fg) in enumerate(cells):
        if i < st or i >= st + span:
            out = out + S(fg, ch)
        elif i == st:
            out = out + slot
    return out + P(" ") + S(DIM, "▏") + P(" ")


def row_label(name):
    return S(LAB, name) + S(DOT, ":") + P(sp(6 - len(name)))


def cell(t, col, past, width, col_boxed, last=False):
    """One value in a grid column. When either value in a column is boxed, the
    other gets blank cells where the box's edges go, so the numbers line up."""
    pad = "" if last else sp(width - len(t))
    if past:
        return S(BAD + BOX, "▕ ") + S(CRIT + BOX, t + pad) + S(BAD + BOX, " ▏")
    if col_boxed:
        out = P("  ") + S(col, t) + P(pad)
        return out if last else out + P("  ")
    return S(col, t) + P(pad)


def grid_row(l1, l2, v1, v2, w1, w2, b1, b2, last=True):
    """Two labeled values, padded to the grid. In a boxed column the box's edge
    stands in for the space after the label: the edge is drawn at the right of
    its cell, so a space before it would look doubled. last=False pads the
    second value too, for a row that goes on to a third column."""
    s1, s2 = ("" if b1 else " "), ("" if b2 else " ")
    out = S(LAB, l1) + S(DOT, ":") + P(sp(3 - len(l1)) + s1)
    out = out + cell(v1[1], v1[2], v1[3], w1, b1) + S(DOT, " · ")
    out = out + S(LAB, l2) + S(DOT, ":") + P(sp(3 - len(l2)) + s2)
    return out + cell(v2[1], v2[2], v2[3], w2, b2, last=last)


def graded_cell(num, w, c, text):
    """A value in the color NUM earns, as (styled, text, color, past_limit)."""
    if num >= c:
        return None, text, CRIT, True
    return None, text, WARN if num >= w else OK, False


def build_left(st, bw, with_third=True):
    """The left rows: 0 Ctx, 1 5h, 2 7d, 3 Fable, and 4 the machine (printed
    above them). Each row's number sits in the middle of its bar. with_third
    False leaves out the third column of values, for a narrow terminal."""
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

    # "Resets" is written once, on the 5h row; the weekly times hang off it
    # tree-style, the times lined up under the 5h one ("Resets: " is 8 wide).
    rows[1] = rows[1] + S(LAB, "Resets") + S(DOT, ":") + P(" ") + S(VAL, st.five_r)
    if st.fable_pct is not None:
        rows[2] = rows[2] + P("  ") + S(DOT, "├────") + P(" ") + S(VAL, st.seven_r)
        rows[3] = rows[3] + P("  ") + S(DOT, "└────") + P(" ") + S(VAL, st.fable_r)
    else:
        rows[2] = rows[2] + P("  ") + S(DOT, "└────") + P(" ") + S(VAL, st.seven_r)
        rows[3] = T()

    # A third column runs down beside them: Temp on the machine row, then Cache,
    # Cost and Turn beside the resets, leaving the Ctx row's slot empty. Each is
    # present only when it has a value.
    third = {}
    if st.have_ismc:
        if st.cpu_temp is None:
            third[4] = ("Temp", (None, "-", DET, False))
        else:
            third[4] = ("Temp", graded_cell(st.cpu_temp, 70, 85, "%d°" % st.cpu_temp))
    if st.cache_pct is not None:
        third[1] = ("Cache", val(st.cache_pct))
    third[2] = ("Cost", graded_cell(int(st.cost.split(".")[0]), 50, 100, "$" + st.cost))
    third[3] = ("Turn", graded_cell(st.turns, 150, 300, str(st.turns)))
    if not with_third:
        third = {}

    # AC · Win and Mem · GPU form a grid: labels pad to the widest in their
    # column, values too.
    a1, a2, m1, m2 = val(st.ac_pct), val(st.win_pct), val(st.mem_pct), val(st.gpu_pct)
    w1, w2 = max(len(a1[1]), len(m1[1])), max(len(a2[1]), len(m2[1]))
    b1, b2 = a1[3] or m1[3], a2[3] or m2[3]
    rows[0] = rows[0] + grid_row("AC", "Win", a1, a2, w1, w2, b1, b2, last=0 not in third)
    rows[4] = rows[4] + grid_row("Mem", "GPU", m1, m2, w1, w2, b1, b2, last=4 not in third)

    # The third column starts where the longest row before it ends. Its labels
    # pad to the longest present, and as in the grid, a boxed value's edge stands
    # in for the space after its label.
    start = max([len(rows[i]) for i in third] or [0])
    lw3 = max([len(lab) for lab, _ in third.values()] or [0])
    vw3 = max([len(v[1]) for _, v in third.values()] or [0])
    bx3 = any(v[3] for _, v in third.values())
    for i, (lab, v) in third.items():
        # Only Temp takes a dot, as the third of Mem · GPU · Temp; the values
        # beside the resets stand apart from the times before them.
        dot = S(DOT, " · ") if i == 4 else P("   ")
        rows[i] = (rows[i] + P(sp(start - len(rows[i]))) + dot + S(LAB, lab) + S(DOT, ":")
                   + P(sp(lw3 - len(lab)) + ("" if bx3 else " ")) + cell(v[1], v[2], v[3], vw3, bx3, last=True))
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


def effort_colored(w, lvl, now):
    """Effort takes the colors of Claude Code's /effort picker. Its animations
    tick every 100 ms; a status line only redraws on events and the refresh
    timer, so xhigh's highlight steps a letter per redraw. Max's rainbow holds
    still, spread end to end across the word, because stepping it popped
    instead of flowing."""
    n = len(w)
    if lvl in EFFORT:
        return S(EFFORT[lvl], w)
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
    return S(VAL, w)


def rate(b):
    """A short rate, right-aligned in 8 columns (840 B/s, 12 KB/s, 1.2 MB/s), so
    the details after it don't shift as the numbers change."""
    b, i, units = float(b), 0, ("B", "KB", "MB", "GB")
    while b >= 999.5 and i < 3:
        b /= 1000
        i += 1
    n = "%.1f" % b if b < 9.95 and i > 0 else "%d" % int(b + 0.5)
    return "%8s" % ("%s %s/s" % (n, units[i]))


def build_right(st, now):
    """The bright part and detail of each right row."""
    br, gr = [T() for _ in range(5)], [T() for _ in range(5)]

    br[0] = S(VAL, st.model) + S(SLASH, "/") + effort_colored(st.effort, st.lvl, now)

    if st.in_git:
        rl1 = "Git"
        br[1] = slashed(st.branch, VAL)
        if st.ahead > 0:
            br[1] = br[1] + P(" ") + S(OK, "↑%d" % st.ahead)
        if st.behind > 0:
            br[1] = br[1] + P(" ") + S(BAD, "↓%d" % st.behind)
        br[1] = br[1] + P(" ") + (S(WARN, "✚%d" % st.dirty) if st.dirty > 0 else S(OK, "✓"))
        gr[1] = slashed(st.sdir, DET)
    else:
        # Outside a repo the folder is the row's only item, so it stays bright.
        rl1 = "Dir"
        br[1] = slashed(st.sdir, VAL)

    br[2] = S(VAL, st.kube)
    if st.ns:
        gr[2] = S(DET, st.ns)

    br[3] = S(VAL, st.sid8)
    if st.sname:
        gr[3] = S(DET, st.sname)

    # The machine row: the network, with lavender arrows and only the rates in
    # their color.
    br[4] = (S(DOT, "↓") + graded(st.rx_bps, 10**6, 10**7, rate(st.rx_bps), nobox=True) + P(" ")
             + S(DOT, "↑") + graded(st.tx_bps, 10**6, 10**7, rate(st.tx_bps), nobox=True))
    return br, gr, ["Model", rl1, "K8s", "ID", "Net"]



def render(st, cols, lines, now):
    br, gr, rlab = build_right(st, now)
    # A short terminal (under 20 rows) leaves out the machine row, so the status
    # line takes four rows instead of five. Everything below measures and prints
    # only the rows in this list, in the order they print.
    order = [0, 1, 2, 3] if lines and 0 < lines < 20 else [4, 0, 1, 2, 3]

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
        # A left row is its label (7), the bar's edges with a space inside each and
        # one after (5), and the bar; a right row starts with its label (7).
        bmin = max([0] + [len(left[i]) - ncpu - 12 for i in order])
        cb, cf = 0, 0
        for i in order:
            cb = max(cb, len(br[i]))
            cf = max(cf, mw + 2 + len(gr[i]) if len(gr[i]) else len(br[i]))
        cb, cf = cb + 7, cf + 7
        # The left side with the bars at one and two characters per core.
        l1, l2 = ncpu + 12 + bmin, 2 * ncpu + 12 + bmin
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
    avail = w_avail if show == "left" else w_avail - 3 - c
    per = pmax
    while per > 1 and per * ncpu + 12 + bmin > avail:
        per -= 1
    # The bars then take every spare column, up to four per core, so no width
    # leaves a gap at the end of the line.
    bw = max(per * ncpu, min(avail - 12 - bmin, pmax * ncpu))
    left = build_left(st, bw, with_third)
    # The values column pads out to the divider by 3 spare columns at most; any
    # other leftover goes at the end of the line, where empty space doesn't show.
    lw = 0 if show == "left" else min(avail, bw + 12 + bmin + 3)
    lw = max([lw] + [len(left[i]) for i in order])

    out = []
    for i in order:
        if show == "left":
            out.append(left[i].ansi())
            continue
        line = left[i].ansi() + sp(lw - len(left[i]))
        line += DIV + " │ " + R + LAB + rlab[i] + R + DOT + ":" + R + sp(6 - len(rlab[i])) + br[i].ansi()
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
    """One reading of the machine is shared by every session for 10 s, so they
    all show the same numbers. The first session past that takes the next one.
    -> cpu, mem, cores, gpu, net in, net out."""
    path = os.path.join(CACHE, "machine-v4")
    if age(path, now) < 10:
        try:
            with open(path) as f:
                p = f.readline().rstrip("\n").split("\t") + [""] * 6
            return (num(p[0]), num(p[1]), [int(x) for x in p[2].split()], num(p[3]), num(p[4]), num(p[5]))
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
    # The kernel's memorystatus level is the share of memory it counts as free.
    mem = 100 - num(run(["sysctl", "-n", "kern.memorystatus_level"]), 100)
    # The GPU's utilization comes from its IOAccelerator entry in the I/O
    # Registry, readable without sudo.
    m = re.search(r'"Device Utilization %"=([0-9]+)', run(["ioreg", "-r", "-d", "1", "-c", "IOAccelerator"]) or "")
    gpu = int(m.group(1)) if m else 0
    # Network: bytes in and out across the en* interfaces (Wi-Fi, Ethernet), as
    # the rate since the previous reading. Loopback and VPN tunnels are left out,
    # since their traffic also crosses a real interface and would be counted twice.
    rx = tx = 0
    for line in (run(["netstat", "-ibn"]) or "").splitlines():
        f = line.split()
        if len(f) >= 5 and re.fullmatch(r"en[0-9]+", f[0]) and f[2].startswith("<Link"):
            rx, tx = rx + num(f[-5]), tx + num(f[-2])
    netc = os.path.join(CACHE, "net-bytes")
    rx_bps = tx_bps = 0
    try:
        with open(netc) as f:
            pt, prx, ptx = (num(x) for x in f.read().split()[:3])
        if now > pt:
            rx_bps = int(float("%.0f" % (max(rx - prx, 0) / (now - pt))))
            tx_bps = int(float("%.0f" % (max(tx - ptx, 0) / (now - pt))))
    except (OSError, ValueError):
        pass
    write_atomic(netc, "%d %d %d\n" % (now, rx, tx))
    write_atomic(path, "%d\t%d\t%s\t%d\t%d\t%d\n" % (cpu, mem, " ".join(map(str, cores)), gpu, rx_bps, tx_bps))
    return cpu, mem, cores, gpu, rx_bps, tx_bps


def read_sensors(now):
    """CPU temperature from iSMC (brew tap dkorunic/tap && brew install ismc),
    which reads the sensors without sudo. It takes about a second, so it runs in
    the background every 10 s and leaves its reading in a cache. -> (have iSMC,
    temperature or None)."""
    if not shutil.which("ismc"):
        return False, None
    sensors, stamp = os.path.join(CACHE, "sensors.json"), os.path.join(CACHE, "sensors.stamp")
    if age(stamp, now) >= 10:
        touch(stamp)
        spawn("--read-sensors")
    if age(sensors, now) < 60:
        try:
            with open(sensors) as f:
                t = json.load(f).get("temp")
            if t not in (None, False, ""):
                return True, jround(t)
        except (OSError, ValueError, AttributeError):
            pass
    return True, None


def refresh_sensors():
    out = run(["ismc", "temp", "-o", "json"])
    try:
        t = jget(json.loads(out), "CPU Die Average", "quantity")
    except (TypeError, ValueError):
        t = None
    write_atomic(os.path.join(CACHE, "sensors.json"), json.dumps({"temp": t}, separators=(",", ":")))


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
    pc = payload.get("prompt_cache") if isinstance(payload, dict) else None
    if not pc or not isinstance(pc, dict) or pc.get("caching_observed") is False:
        cwarm = "none"
    else:
        cwarm = jq_text(pc.get("warm")) if pc.get("warm") is not None else "null"
    cttl = jget(payload, "prompt_cache", "ttl", default="-")
    cexp = num(jget(payload, "prompt_cache", "expires_at", default=0))
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
    st.kube, st.ns = "none", ""
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

    st.fable_pct, fable_reset = read_fable(now)
    st.fable_r = fmt_reset(fable_reset, now)

    st.ncpu = os.cpu_count() or 1
    st.cpu_pct, st.mem_pct, st.cores, st.gpu_pct, st.rx_bps, st.tx_bps = read_machine(now, st.ncpu)
    st.have_ismc, st.cpu_temp = read_sensors(now)
    st.turns = read_turns(tpath, sid)

    st.sdir = short_dir(st.dir)
    # Branch names stop at 20 characters so one long name can't push the grey column away.
    if len(st.branch) > 20:
        st.branch = st.branch[:19] + "…"
    st.sid8 = sid[:8]

    # The prompt cache shows how much of its life (5m or 1h) has gone: it fills
    # toward trouble like every other percentage, and at 100% the next message
    # pays to rebuild the whole context. Hidden until a response has reported caching.
    st.cache_pct = None
    if cwarm == "false":
        st.cache_pct = 100
    elif cwarm == "true" and cexp > 0:
        ttl = 300 if cttl == "5m" else 3600
        n = (ttl - (cexp - now)) * 100 + ttl // 2
        q = abs(n) // ttl * (1 if n >= 0 else -1)
        st.cache_pct = max(0, min(100, q))
    return st


def main():
    if sys.argv[1:] == ["--read-sensors"]:
        refresh_sensors()
        return
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
        out = render(st, num(os.environ.get("COLUMNS"), 145), num(os.environ.get("LINES"), 0), st.now)
    except Exception as e:  # a broken status line should still say why
        out = "statusline.py: %s: %s" % (type(e).__name__, e)
    sys.stdout.buffer.write(out.encode("utf-8"))


if __name__ == "__main__":
    main()
