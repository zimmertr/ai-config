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
        cpu_pct=10, cores=[30, 20, 10, 5, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8], ncpu=14,
        in_git=True, branch="main", ahead=0, behind=7, dirty=2, sdir="~/git/personal/bluebird",
        kube="admin@stable", ns="default", sid8="1feba53f", cost="3.63", turns=220, sname="claude-00",
        five_pace=111, seven_pace=164, fable_pace=167,
    )
    for k, v in kw.items():
        setattr(st, k, v)
    return st


# The states the layout has to hold up in: every value past its limit, a long
# branch and session name, outside a repo, and each optional part missing.
STATES = {
    "typical": state(),
    "all boxed": state(ac_pct=120, win_pct=95, five_pct=88, seven_pct=100, cpu_pct=99,
                       cost="140.00", turns=400, five_pace=160, seven_pace=190, fable_pace=200, cores=[100] * 14),
    "long names": state(branch="feat/a-very-long-branch-nam…", sname="a-session-name-that-runs-long",
                        sdir="~/.claude/tmp/…/scratchpad", kube="arn:aws:eks:us-west-2:cluster/x"),
    "no git": state(in_git=False, sdir="/"),
    "no fable": state(fable_pct=None),
    "no pace yet": state(five_pace=None, seven_pace=None, fable_pace=None),
    "no cores": state(cores=[]),
    "no namespace": state(kube="", ns=""),
    "8 cores": state(ncpu=8, cores=[50, 40, 30, 20, 10, 0, 90, 80]),
    "xhigh": state(effort="Xhigh", lvl="xhigh"),
    "max": state(effort="Max", lvl="max"),
}

SIZES = list(range(60, 221, 7))


def rows(st, cols):
    return [plain(r) for r in sl.render(st, cols, NOW).split("\n")]


# --- Layout ---
@pytest.mark.parametrize("name", STATES)
@pytest.mark.parametrize("cols", SIZES)
def test_every_line_fits(name, cols):
    for r in rows(STATES[name], cols):
        assert len(r) <= cols - 5, r


@pytest.mark.parametrize("name", STATES)
@pytest.mark.parametrize("cols", SIZES)
def test_divider_in_one_column(name, cols):
    at = {r.find(" │ ") for r in rows(STATES[name], cols)}
    assert len(at) == 1


@pytest.mark.parametrize("name", STATES)
@pytest.mark.parametrize("cols", SIZES)
def test_no_box_is_cut_open(name, cols):
    for r in rows(STATES[name], cols):
        assert r.count("▕") == r.count("▏"), r


@pytest.mark.parametrize("name", STATES)
@pytest.mark.parametrize("cols", SIZES)
def test_grids_line_up(name, cols):
    rs = rows(STATES[name], cols)
    machine, ctx = rs[0], rs[1]
    assert machine.index("AC:") == ctx.index("Win:")
    # Cost and Turn start in one column, the 𝐏 tree's branches start there too,
    # and their numbers line up; the paces drop on a narrow terminal.
    heads = [(machine, machine.index("Cost:")), (ctx, ctx.index("Turn:"))]
    if "𝐏" in rs[2]:
        for r in rs[2:]:
            g = [m.start() for m in re.finditer("[𝐏├└]", r)]
            if "𝐏" in r or len(g) > 1:
                heads.append((r, g[-1]))
    assert len({h for _, h in heads}) == 1, rs
    nums = {next(j for j in range(h + 4, len(r)) if r[j] in "0123456789$–") for r, h in heads}
    assert len(nums) == 1, rs
    if cols >= 140:
        assert "𝐏" in rs[2]


def test_third_column_drops_before_the_right_side():
    rs = rows(state(), 80)
    assert "𝐏" not in rs[2] and " │ Dir:" in rs[2]


@pytest.mark.parametrize("name", STATES)
def test_bars_share_a_width(name):
    # The divider after each bar is the first │ drawn in icy blue.
    edge = sl.DIV + "│"
    # Without Fable its row has no bar.
    ends = {len(plain(r[:r.index(edge)])) for r in sl.render(STATES[name], 160, NOW).split("\n") if edge in r}
    assert len(ends) == 1


def test_always_five_rows():
    """Model is on the top row, so a short terminal keeps every row."""
    assert len(rows(state(), 145)) == 5


def test_folder_has_its_own_row():
    rs = rows(state(), 160)
    labels = [r.split(" │ ")[-1].split(":")[0] for r in rs]
    assert labels == ["Model", "ID", "Dir", "Git", "K8s"]
    assert "Dir:   ~/git/personal/bluebird" in rs[2] and "bluebird" not in rs[3]
    assert rows(state(in_git=False), 160)[3].endswith("Git:   –")
    assert "K8s:   –" in rows(state(kube=""), 160)[4]


def test_narrow_terminal_trims_details_before_the_right_side():
    wide, narrow = rows(state(), 200), rows(state(), 120)
    assert "claude-00" in wide[1]
    assert "Model:" in narrow[0] and "Dir:" in narrow[2]
    assert "𝐏" in narrow[2] and "Cost:" in narrow[0] and "Turn:" in narrow[1]


def test_very_narrow_terminal_keeps_only_the_bars():
    rs = rows(state(ncpu=24, cores=[]), 50)
    assert all("Model:" not in r and "Dir:" not in r for r in rs)


def test_number_sits_in_the_middle_of_its_bar():
    r = rows(state(), 160)[2]  # 5h
    bar = r[7:r.index(" │ ")]
    i = bar.index("2%")
    assert abs(i - (len(bar) - i - 2)) <= 3


def test_effort_keeps_its_word():
    for lvl in ("low", "medium", "high", "xhigh", "max", "other"):
        for now in range(10):
            assert sl.effort_colored("Word", lvl, now).plain == "Word"


# --- Helpers ---
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


@pytest.mark.parametrize("pct,left,want", [
    (49, 10_040, 111),      # 49% used, 44% of the window gone
    (10, 9_000, 20),        # half the window gone
    (5, 18_000 - 600, None),  # 10 minutes in: too early to say
    (0, 0, None),           # no reset known
])
def test_pace(pct, left, want):
    assert sl.pace(pct, NOW + left if left else 0, 5 * 3600, NOW) == want


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
