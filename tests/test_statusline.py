"""Tests for claude/statusline.py.

The helpers are checked against known answers. The layout is checked by the
rules it has to keep at every size: each line fits the width Claude Code gives
it, the divider lands in one column, a box is never cut open, and the grids line
up.
"""

import json
import os
import re
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "claude"))
import statusline as sl  # noqa: E402

NOW = 1_800_000_000
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def plain(text):
    return ANSI.sub("", text)


def state(**kw):
    st = SimpleNamespace(
        model="Opus 5.5", effort="High", lvl="high",
        ctx_tok=191_093, win=1_000_000, ac_pct=39, win_pct=19,
        five_pct=2, seven_pct=92, fable_pct=100,
        five_r="4h46m", seven_r="2d21h", fable_r="2d21h",
        cpu_pct=10, mem_pct=32, gpu_pct=0, cores=[30, 20, 10, 5, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8], ncpu=14,
        in_git=True, branch="main", ahead=0, behind=7, dirty=2, sdir="~/git/personal/bluebird",
        kube="admin@stable", ns="default", sid8="1feba53f", cost="3.63", turns=220, sname="claude-00",
        rx_bps=5_700, tx_bps=4_500, have_ismc=True, cpu_temp=45, cache_pct=100,
    )
    for k, v in kw.items():
        setattr(st, k, v)
    return st


# The states the layout has to hold up in: every value past its limit, a long
# branch and session name, outside a repo, and each optional part missing.
STATES = {
    "typical": state(),
    "all boxed": state(ac_pct=120, win_pct=95, five_pct=88, seven_pct=100, cpu_pct=99, mem_pct=91, gpu_pct=85,
                       cost="140.00", turns=400, cpu_temp=90, cache_pct=100, cores=[100] * 14),
    "long names": state(branch="feat/a-very-long-branch-nam…", sname="a-session-name-that-runs-long",
                        sdir="~/.claude/tmp/…/scratchpad", kube="arn:aws:eks:us-west-2:cluster/x"),
    "no git": state(in_git=False, sdir="/"),
    "no fable": state(fable_pct=None),
    "no ismc": state(have_ismc=False, cpu_temp=None),
    "no temp yet": state(cpu_temp=None),
    "no cache": state(cache_pct=None),
    "no cores": state(cores=[]),
    "no namespace": state(kube="none", ns=""),
    "8 cores": state(ncpu=8, cores=[50, 40, 30, 20, 10, 0, 90, 80]),
    "xhigh": state(effort="Xhigh", lvl="xhigh"),
    "max": state(effort="Max", lvl="max"),
}

SIZES = [(c, l) for c in range(60, 221, 7) for l in (15, 66)]


def rows(st, cols, lines):
    return [plain(r) for r in sl.render(st, cols, lines, NOW).split("\n")]


# --- Layout ---
@pytest.mark.parametrize("name", STATES)
@pytest.mark.parametrize("cols,lines", SIZES)
def test_every_line_fits(name, cols, lines):
    for r in rows(STATES[name], cols, lines):
        assert len(r) <= cols - 5, r


@pytest.mark.parametrize("name", STATES)
@pytest.mark.parametrize("cols,lines", SIZES)
def test_divider_in_one_column(name, cols, lines):
    at = {r.find(" │ ") for r in rows(STATES[name], cols, lines)}
    assert len(at) == 1


@pytest.mark.parametrize("name", STATES)
@pytest.mark.parametrize("cols,lines", SIZES)
def test_no_box_is_cut_open(name, cols, lines):
    for r in rows(STATES[name], cols, lines):
        assert r.count("▕") == r.count("▏"), r


@pytest.mark.parametrize("name", STATES)
@pytest.mark.parametrize("cols", [c for c, _ in SIZES])
def test_grids_line_up(name, cols):
    rs = rows(STATES[name], cols, 66)
    machine, ctx = rs[0], rs[1]
    assert machine.index("Mem:") == ctx.index("AC:")
    assert machine.index("GPU:") == ctx.index("Win:")
    # The third column: Temp, Cache, Cost and Turn start in one column, or all
    # drop together on a narrow terminal.
    third = [r.index(lab) for r, lab in ((machine, "Temp:"), (rs[2], "Cache:"), (rs[3], "Cost:"), (rs[4], "Turn:")) if lab in r]
    assert len(set(third)) <= 1, rs
    if cols >= 140:
        assert "Cost:" in rs[3] and "Turn:" in rs[4] and "·" not in ctx[ctx.index("Win:"):]


def test_third_column_drops_before_the_right_side():
    rs = rows(state(), 81, 66)
    assert "Cache:" not in rs[2] and " │ Git:" in rs[2]


@pytest.mark.parametrize("name", STATES)
def test_bars_share_a_width(name):
    # A bar's closing edge is the only ▏ drawn in its dim grey.
    edge = sl.DIM + "▏"
    # Without Fable its row has no bar.
    ends = {len(plain(r[:r.index(edge)])) for r in sl.render(STATES[name], 160, 66, NOW).split("\n") if edge in r}
    assert len(ends) == 1


def test_short_terminal_drops_the_machine_row():
    assert len(rows(state(), 145, 66)) == 5
    rs = rows(state(), 145, 19)
    assert len(rs) == 4 and rs[0].startswith("Ctx:")
    assert len(rows(state(), 145, 20)) == 5


def test_narrow_terminal_trims_details_before_the_right_side():
    wide, narrow = rows(state(), 200, 66), rows(state(), 120, 66)
    assert "claude-00" in wide[4]
    assert "Model:" in narrow[1] and "Net:" in narrow[0]
    assert "Cost:" in narrow[3] and "Turn:" in narrow[4]


def test_very_narrow_terminal_keeps_only_the_bars():
    rs = rows(state(ncpu=24, cores=[]), 50, 66)
    assert all(" │ " not in r for r in rs)


def test_number_sits_in_the_middle_of_its_bar():
    r = rows(state(), 160, 66)[2]  # 5h
    bar = r[r.index("▕") + 2:r.index(" ▏")]
    i = bar.index("2%")
    assert abs(i - (len(bar) - i - 2)) <= 3


def test_effort_keeps_its_word():
    for lvl in ("low", "medium", "high", "xhigh", "max", "other"):
        for now in range(10):
            assert sl.effort_colored("Word", lvl, now).plain == "Word"


# --- Helpers ---
@pytest.mark.parametrize("b,want", [
    (0, "0 B/s"), (840, "840 B/s"), (999, "999 B/s"), (999.5, "1.0 KB/s"), (12_400, "12 KB/s"),
    (9_940, "9.9 KB/s"), (9_950, "10 KB/s"), (1_234_567, "1.2 MB/s"), (5e12, "5000 GB/s"),
])
def test_rate(b, want):
    assert sl.rate(b) == "%8s" % want


@pytest.mark.parametrize("d,want", [
    (None, "-"), (-5, "now"), (59, "0m"), (61, "1m"), (3600, "1h0m"), (3 * 3600 + 7 * 60, "3h7m"),
    (172_799, "47h59m"), (172_800, "2d0h"), (3 * 86400 + 5 * 3600, "3d5h"),
])
def test_fmt_reset(d, want):
    assert sl.fmt_reset(0 if d is None else NOW + d, NOW) == want


@pytest.mark.parametrize("p,want", [
    ("~/git/personal/bluebird", "~/git/personal/bluebird"),
    ("~/.claude/tmp/claude-501/-Users-tj--claude/1feba53f/scratchpad", "~/.claude/tmp/…/scratchpad"),
    ("/a-very-long-folder-name/another-one/", "/a-very-long-folder-name/another-one/"),
    ("/one/two/three/four/five-and-something-long/", "/one/two/…/five-and-something-long"),
])
def test_short_dir(p, want):
    assert sl.short_dir(p) == want


@pytest.mark.parametrize("v,bare,want", [
    ("200000", False, 200_000), ("200k", False, 200_000), ("1M", False, 1_000_000), ("0.5m", False, 500_000),
    ("400", False, None), ("400", True, 400_000), ("2m", False, None), ("50k", False, None),
    ("", False, None), ("abc", False, None), ("1e5", False, None),
])
def test_to_tokens(v, bare, want):
    assert sl.to_tokens(v, bare) == want


@pytest.mark.parametrize("win,mid,env,settings,want", [
    (200_000, "", {}, {}, 167_000),
    (200_000, "", {"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50"}, {}, 90_000),
    (200_000, "", {"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "0"}, {}, 167_000),
    (200_000, "", {"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "150"}, {}, 167_000),
    (1_000_000, "", {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "300k"}, {}, 267_000),
    (1_000_000, "m", {}, {"autoCompactWindow": 400, "modelSettings": {"m": {"autoCompactWindow": "500k"}}}, 467_000),
    (1_000_000, "x", {}, {"autoCompactWindow": 400, "modelSettings": {"m": {"autoCompactWindow": "500k"}}}, 367_000),
    (200_000, "", {}, {"autoCompactWindow": "400k"}, 167_000),
    (1_000_000, "", {"CLAUDE_CODE_AUTO_COMPACT_WINDOW": "300k"}, {"autoCompactWindow": "500k"}, 267_000),
])
def test_ac_threshold(win, mid, env, settings, want):
    assert sl.ac_threshold(win, mid, env, settings) == want


def test_merge_limits_keeps_the_newest():
    old = json.dumps({"five": {"pct": 30, "reset": 100}, "seven": {"pct": 60, "reset": 500}})
    text, five, seven = sl.merge_limits(old, (10, 200), (50, 500))
    assert five == (10, 200)   # a later reset is a newer window
    assert seven == (60, 500)  # within one window usage only climbs
    assert json.loads(text) == {"five": {"pct": 10, "reset": 200}, "seven": {"pct": 60, "reset": 500}}
    assert " " not in text


def test_merge_limits_starts_from_nothing():
    _, five, seven = sl.merge_limits("{}", (5, 100), (0, 0))
    assert five == (5, 100) and seven == (0, 0)


def test_merge_limits_skips_a_broken_file():
    assert sl.merge_limits("not json", (5, 100), (0, 0)) is None


def test_count_turns():
    data = b'{"promptId":"a"}\n{"promptId":"a"}\n{"promptId":"b"}\n{"promptId":"a"}\n'
    assert sl.count_turns(data, "") == (2, '"promptId":"a"')
    # The last prompt of the previous read isn't counted again.
    assert sl.count_turns(b'{"promptId":"a"}{"promptId":"c"}', '"promptId":"a"') == (1, '"promptId":"c"')
    assert sl.count_turns(b"", '"promptId":"z"') == (0, '"promptId":"z"')


def test_read_turns_reads_only_what_was_added(tmp_path, monkeypatch):
    monkeypatch.setattr(sl, "CACHE", str(tmp_path / "cache"))
    t = tmp_path / "t.jsonl"
    t.write_bytes(b'{"promptId":"a"}\n{"promptId":"b"}\n')
    assert sl.read_turns(str(t), "s") == 2
    with t.open("ab") as f:
        f.write(b'{"promptId":"b"}\n{"promptId":"c"}\n')
    assert sl.read_turns(str(t), "s") == 3
    t.write_bytes(b'{"promptId":"x"}\n')  # a shorter file is a new transcript
    assert sl.read_turns(str(t), "s") == 1


def test_bar_shows_a_sliver():
    assert [c for c, _ in sl.bar(1, 1000, sl.OK, 10)].count("▰") == 1
    assert [c for c, _ in sl.bar(0, 1000, sl.OK, 10)].count("▰") == 0
    assert [c for c, _ in sl.bar(2000, 1000, sl.OK, 10)].count("▰") == 10


def test_jround_rounds_halves_away_from_zero():
    assert [sl.jround(x) for x in (0.5, 1.5, 2.5, -0.5, 2.4, None)] == [1, 2, 3, -1, 2, 0]


# --- End to end ---
def test_script_prints_five_rows_anywhere(tmp_path):
    """collect() reads macOS commands; elsewhere they are missing and the script
    must still print, and exit 0, since Claude Code hides the line otherwise."""
    payload = {"model": {"display_name": "Opus 5.5"}, "effort": {"level": "high"},
               "context_window": {"total_input_tokens": 50_000, "context_window_size": 200_000},
               "session_id": "abc", "workspace": {"current_dir": str(tmp_path)}}
    env = {"HOME": str(tmp_path), "PATH": os.environ.get("PATH", ""), "COLUMNS": "145", "LINES": "66"}
    script = os.path.join(os.path.dirname(__file__), "..", "claude", "statusline.py")
    p = subprocess.run([sys.executable, script], input=json.dumps(payload).encode(), env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    assert p.returncode == 0
    out = p.stdout.decode()
    assert "statusline.py:" not in out, out
    assert len(out.split("\n")) == 5


def test_script_survives_a_bad_payload(tmp_path):
    env = {"HOME": str(tmp_path), "PATH": os.environ.get("PATH", "")}
    script = os.path.join(os.path.dirname(__file__), "..", "claude", "statusline.py")
    p = subprocess.run([sys.executable, script], input=b"not json", env=env,
                       stdout=subprocess.PIPE, timeout=30)
    assert p.returncode == 0 and p.stdout
