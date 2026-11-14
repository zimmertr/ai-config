#!/usr/bin/env bash
# Claude Code status line. Reads session-context JSON on stdin and prints five
# rows: the machine on top, then a bar for context and each usage limit on the
# left, and what the session is working with on the right. The layout sizes
# itself to the terminal's width. Wired via ~/.claude/settings.json as
# `bash ~/.claude/statusline.sh`.
#
#   CPU:   ▕▄▄▄▄▄▄▄▄▄▃▃▃▁▁▁▁    17%   ▁▂▂▂▂▂▂▂▂▂▁▁▁▁▁▁▏ Mem: 60% · Swap: ▕ 16G ▏   │ Net:     ↓3.5 KB/s ↑4.3 KB/s  Temp: 46°
#   Ctx:   ▕▰▰▰▰▰▰▰▰▱▱▱▱▱▱▱▱   191k   ▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▏ AC: 39% · Win: 19%         │ Model:   Opus 5.5/High        Cache: ▕ 100% ▏
#   5h:    ▕▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰    38%   ▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▏ Resets: 1h5m               │ Git:     main ↓7 ✚2           ~/git/personal/bluebird
#   7d:    ▕▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰ ▕  90% ▏ ▰▰▰▰▰▰▰▰▰▰▰▰▱▱▱▱▏   ├──── 2d22h              │ K8s:     admin@stable         default
#   Fable: ▕▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰ ▕ 100% ▏ ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▏   └──── 2d22h              │ Session: 1feba53f             $3.63 · Turn: 195 · claude-00
#
# The ctx bar spans the model's whole window. AC is the share of the point where
# auto-compact fires, Win the share of the whole window. With auto-compact on,
# Win can never pass the AC point, so it only matters when compaction is off
# (DISABLE_AUTO_COMPACT=1). The Fable row is hidden until the Fable limit has
# been fetched (see below). The Git row reads Dir outside a repo; ↑/↓ track the
# branch's own upstream, ✚ counts changed files. Cache is how much of the prompt
# cache's life has gone since the last message.
#
# One color per job: mauve labels a value, white is a value, slate teal is the
# minor detail that ends a row, lavender dots sit between items, icy blue draws
# the dividers, and mint / gold / coral is a value with a limit: mint under 50%,
# gold under 80%, and from 80% bold coral, boxed by coral edges with a line above
# and below. Ctx's token count takes AC's color. The bars fill in quieter tones
# with the same steps: steel blue, soft violet, orchid.
#
# The session's short name (`claude-80`) is what other sessions message it by;
# the 8-character ID prefix is what create-issue labels its issues with.

# ${#var} must count characters, not bytes, for the columns to line up around
# the bar and box-drawing glyphs; the status line can start under the C locale.
export LC_ALL=en_US.UTF-8

input=$(cat)

IFS=$'\t' read -r model effort win_pct ctx_tok five_pct five_reset seven_pct seven_reset cost sid win cwarm cttl cexp mid <<EOF
$(echo "$input" | jq -r '[
  .model.display_name // "?",
  (.effort.level // "?"),
  (.context_window.used_percentage // 0 | round),
  (.context_window.total_input_tokens // 0),
  (.rate_limits.five_hour.used_percentage // 0 | round),
  (.rate_limits.five_hour.resets_at // 0),
  (.rate_limits.seven_day.used_percentage // 0 | round),
  (.rate_limits.seven_day.resets_at // 0),
  (.cost.total_cost_usd // 0),
  (.session_id // "?"),
  (.context_window.context_window_size // 0),
  (if (.prompt_cache // null) == null or .prompt_cache.caching_observed == false
     then "none" else (.prompt_cache.warm | tostring) end),
  (.prompt_cache.ttl // "-"),
  (.prompt_cache.expires_at // 0),
  (.model.id // "")
] | @tsv')
EOF

# An empty or malformed payload leaves these blank; zero keeps the arithmetic below quiet.
: "${win_pct:=0}" "${ctx_tok:=0}" "${five_pct:=0}" "${five_reset:=0}" "${seven_pct:=0}" "${seven_reset:=0}" "${cost:=0}" "${win:=0}" "${cwarm:=none}" "${cexp:=0}"

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
tpath=$(echo "$input" | jq -r '.transcript_path // empty')
dir="${cwd/#$HOME/~}"

# The short session name is not in the stdin payload: Claude Code's messaging
# registry keeps it per process in ~/.claude/sessions/<pid>.json, keyed by the
# same session id. A session started without messaging has no entry.
sname=$(jq -r --arg sid "$sid" 'select(.sessionId == $sid) | .name // empty' \
  "$HOME"/.claude/sessions/*.json 2>/dev/null | head -1)
lvl=$(printf '%s' "$effort" | tr '[:upper:]' '[:lower:]')
effort=$(printf '%s' "$effort" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')

# One git call gives the branch, ahead/behind and changed files. A plain status
# takes the index lock to refresh it, and with the status line re-running on a
# timer that lock can collide with an agent's own git command in the same repo
# ("index.lock exists"), so it runs without the optional locks.
in_git=0; branch=""; dirty=0; ahead=0; behind=0
if gs=$(git -C "$cwd" --no-optional-locks status --porcelain=v2 --branch 2>/dev/null); then
  in_git=1
  IFS=$'\t' read -r branch ahead behind dirty <<EOF
$(printf '%s\n' "$gs" | awk '
  /^# branch\.head /        { h = $3 }
  /^# branch\.ab /          { a = substr($3, 2); b = substr($4, 2) }
  !/^# /                    { n++ }
  END { printf "%s\t%d\t%d\t%d", (h == "(detached)" ? "detached" : h), a, b, n }')
EOF
fi

# K8s context + namespace (namespace needs a second query; only when a context is set)
kube="none"; ns=""
if command -v kubectl >/dev/null 2>&1; then
  c=$(kubectl config current-context 2>/dev/null)
  if [ -n "$c" ]; then
    kube="$c"
    ns=$(kubectl config view --minify -o jsonpath='{..namespace}' 2>/dev/null)
    [ -z "$ns" ] && ns="default"
  fi
fi

ctxk=$(( ctx_tok / 1000 ))
sc=$(printf '%.2f' "$cost")

# --- Auto-compact threshold ---
# The payload says how big the window is but not where auto-compact fires, so
# that is rebuilt from the CLI's own formula (checked against the 2.1.312 binary):
#   window    = context_window_size, lowered by an auto-compact window override
#               (CLAUDE_CODE_AUTO_COMPACT_WINDOW > modelSettings.<id> > autoCompactWindow)
#   effective = window - 20000            # reserved for the model's output
#   threshold = effective - 13000         # reserved for the compaction summary
#   with CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=p: threshold = min(effective*p/100, threshold)
# Those env vars reach this script because settings.json `env` is applied to the
# CLI process and inherited here. A one-off `claude --autocompact N` is invisible.
to_tokens() {   # "200000" | "200k" | "1M" -> tokens if 100K..1M, else empty.
  # $2=1 also reads a bare 100..1000 as thousands, as /autocompact and the setting do.
  awk -v v="$1" -v bare="${2:-0}" 'BEGIN{
    n=tolower(v); m=1
    if (n ~ /k$/) { m=1000; sub(/k$/,"",n) } else if (n ~ /m$/) { m=1000000; sub(/m$/,"",n) }
    if (n !~ /^[0-9]+(\.[0-9]+)?$/) exit
    t=n*m; if (bare==1 && m==1 && t>=100 && t<=1000) t*=1000
    if (t>=100000 && t<=1000000) printf "%d", t }'
}
[ "$win" -gt 0 ] 2>/dev/null || win=200000
acwin="$win"
ov=$(to_tokens "${CLAUDE_CODE_AUTO_COMPACT_WINDOW:-}")
[ -z "$ov" ] && ov=$(to_tokens "$(jq -r --arg m "$mid" \
  '.modelSettings[$m].autoCompactWindow // .autoCompactWindow // empty' \
  "$HOME/.claude/settings.json" 2>/dev/null)" 1)
[ -n "$ov" ] && [ "$ov" -lt "$acwin" ] && acwin="$ov"
ac_thr=$(awk -v w="$acwin" -v p="${CLAUDE_AUTOCOMPACT_PCT_OVERRIDE:-}" 'BEGIN{
  e=w-20000; t=e-13000
  if (p+0>0 && p+0<=100) { o=int(e*p/100); if (o<t) t=o }
  printf "%d", t }')
ac_pct=$(awk -v u="$ctx_tok" -v t="$ac_thr" 'BEGIN{ printf "%d", (t>0 ? u/t*100+0.5 : 0) }')

now=$(date +%s)
fmt_reset() {
  [ "$1" -le 0 ] 2>/dev/null && { printf -- '-'; return; }
  d=$(( $1 - now ))
  [ "$d" -le 0 ] && { printf 'now'; return; }
  if   [ "$d" -ge 172800 ]; then printf '%dd%dh' "$(( d / 86400 ))" "$(( (d % 86400) / 3600 ))"
  elif [ "$d" -ge 3600 ];   then printf '%dh%dm' "$(( d / 3600 ))"  "$(( (d % 3600) / 60 ))"
  else                           printf '%dm'    "$(( d / 60 ))"
  fi
}
# --- Shared usage limits ---
# Each session's payload only refreshes its limits when that session gets an API
# reply, so an idle session would show stale numbers, or none at all before its
# first reply. The limits are account-wide, so every session pools what it has
# seen in one file and shows the newest. No timestamps are needed: a later reset
# time is a newer window, and within one window usage only climbs.
limits_cache="$HOME/.claude/cache/usage-limits.json"
old=$(cat "$limits_cache" 2>/dev/null); [ -n "$old" ] || old='{}'
if merged=$(printf '%s' "$old" | jq -c \
    --argjson fp "$five_pct" --argjson fr "$five_reset" \
    --argjson sp "$seven_pct" --argjson sr "$seven_reset" '
  def newer(a; b): if (b.reset // 0) > (a.reset // 0) then b
    elif (b.reset // 0) == (a.reset // 0) and (b.pct // 0) > (a.pct // 0) then b else a end;
  { five:  newer(.five  // {}; {pct: $fp, reset: $fr}),
    seven: newer(.seven // {}; {pct: $sp, reset: $sr}) }' 2>/dev/null); then
  if [ "$merged" != "$old" ]; then
    mkdir -p "${limits_cache%/*}"
    printf '%s' "$merged" > "$limits_cache.$$" && mv -f "$limits_cache.$$" "$limits_cache"
  fi
  IFS=$'\t' read -r five_pct five_reset seven_pct seven_reset <<EOF
$(printf '%s' "$merged" | jq -r '[.five.pct // 0, .five.reset // 0, .seven.pct // 0, .seven.reset // 0] | @tsv')
EOF
fi
# A window whose reset has passed starts again from zero.
[ "$five_reset"  -gt 0 ] && [ "$five_reset"  -le "$now" ] && { five_pct=0;  five_reset=0; }
[ "$seven_reset" -gt 0 ] && [ "$seven_reset" -le "$now" ] && { seven_pct=0; seven_reset=0; }

five_r=$(fmt_reset "$five_reset")
seven_r=$(fmt_reset "$seven_reset")

# Fable model-scoped weekly limit — not in the stdin payload, so it's pulled from
# the OAuth usage endpoint (same source as /usage) and cached; a background
# refresh at most every 5 min keeps the render itself fast and offline-safe.
fable_cache="$HOME/.claude/cache/fable-limit.json"
fable_stamp="$HOME/.claude/cache/fable-limit.stamp"
IFS=$'\t' read -r fable_pct fable_reset <<EOF
$(jq -r '[(.percent // ""), (.resets_at // "" | sub("\\.[0-9]+"; "") | sub("\\+00:00$"; "Z") | (fromdateiso8601? // 0))] | @tsv' "$fable_cache" 2>/dev/null)
EOF
case "$fable_pct" in ''|*[!0-9]*) fable_pct="" ;; esac
# Cache mtime tracks data freshness (only rewritten on a successful fetch); if
# the data is >3h old (expired token, extended offline) hide it rather than
# show a number that may be days out of date.
fable_age=999999
[ -f "$fable_cache" ] && fable_age=$(( now - $(stat -f %m "$fable_cache" 2>/dev/null || echo 0) ))
[ "$fable_age" -ge 10800 ] && fable_pct=""
fable_r=$(fmt_reset "${fable_reset:-0}")
# The stamp paces fetch *attempts* (touched up front, success or not) so a
# failing fetch retries every 5 min instead of on every render.
attempt_age=999999
[ -f "$fable_stamp" ] && attempt_age=$(( now - $(stat -f %m "$fable_stamp" 2>/dev/null || echo 0) ))
if [ "$attempt_age" -ge 300 ]; then
  touch "$fable_stamp" 2>/dev/null
  (
    tok=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null | jq -r '.claudeAiOauth.accessToken // empty')
    [ -z "$tok" ] && tok=$(jq -r '.claudeAiOauth.accessToken // empty' "$HOME/.claude/.credentials.json" 2>/dev/null)
    [ -z "$tok" ] && exit 0
    out=$(curl -s --max-time 5 https://api.anthropic.com/api/oauth/usage \
      -H "Authorization: Bearer $tok" -H "anthropic-beta: oauth-2025-04-20" \
      | jq -c '[.limits[]? | select(.kind == "weekly_scoped"
                and (.scope.model.display_name // "" | test("fable"; "i")))][0] // empty' 2>/dev/null)
    [ -n "$out" ] && printf '%s' "$out" > "$fable_cache"
  ) >/dev/null 2>&1 &
fi

# --- Palette ---
# Real escape bytes, printed with %s, so a backslash in a branch or path prints as-is.
LAB=$'\033[38;5;139m'   # mauve: labels
DIV=$'\033[38;5;153m'   # icy pale blue: the dividers and the compaction mark
VAL=$'\033[97m'         # white: values
DET=$'\033[38;5;66m'    # slate teal: the minor detail that ends a row
DOT=$'\033[38;5;103m'   # lavender: the dots between items
DIM=$'\033[38;5;243m'   # dim grey: the bar's edges
OK=$'\033[38;5;151m'; WARN=$'\033[38;5;222m'; BAD=$'\033[38;5;210m'   # mint, gold, coral
# The bars fill in quieter tones from the same palette, so a long bar doesn't
# shout over the numbers beside it.
BAR_OK=$'\033[38;5;110m'; BAR_WARN=$'\033[38;5;140m'; BAR_BAD=$'\033[38;5;175m'   # steel blue, soft violet, orchid
CRIT=$'\033[1;38;5;210m'   # bold coral: a value past its limit
BOX=$'\033[4;53m'          # underline and overline: with coral edges, a box around it
# boxed PLAIN -> CP_/CC_: a value past its limit, framed by coral edges with a
# line above and below. Each part restates BOX, since every reset clears it.
boxed() { CP_="▕ $1 ▏"; CC_="${BAD}${BOX}▕ ${R}${CRIT}${BOX}$1${R}${BAD}${BOX} ▏${R}"; }
EMPTY=$'\033[38;5;237m'; R=$'\033[0m'

# Each row is built twice: P* holds the plain text (for measuring) and C* the
# colored text (for printing). ap ROW PLAIN COLORED appends to one left row.
LP=(); LC=(); RP=(); RC=()
ap() { LP[$1]="${LP[$1]}$2"; LC[$1]="${LC[$1]}$3"; }
spaces() { [ "$1" -gt 0 ] && printf '%*s' "$1" ''; }

# graded NUM WARN CRIT TEXT [nobox] -> GP_/GC_: TEXT in the color NUM earns.
# nobox keeps a value past its limit plain coral, for a value whose width must
# hold still because the details after it line up.
graded() {
  if [ "$1" -ge "$3" ]; then
    if [ -n "$5" ]; then GP_=$4; GC_="${CRIT}$4${R}"; else boxed "$4"; GP_=$CP_; GC_=$CC_; fi
  elif [ "$1" -ge "$2" ]; then GP_=$4; GC_="${WARN}$4${R}"
  else GP_=$4; GC_="${OK}$4${R}"; fi
}

# val VALUE [WARN=50] [CRIT=80] -> VP/VC, plus VR (the bare text), VK (its
# color) and VX (1 past the limit) for a bar to frame itself.
val() {
  local w=${2:-50} c=${3:-80}
  VR="$1%"; VX=""
  if   [ "$1" -ge "$c" ]; then boxed "$1%"; VP=$CP_; VC=$CC_; VK=$CRIT; VX=1
  elif [ "$1" -ge "$w" ]; then VP="$1%";  VC="${WARN}$1%${R}"; VK=$WARN
  else                         VP="$1%";  VC="${OK}$1%${R}"; VK=$OK; fi
}

# --- Bars ---
# BW segments, a whole number per core (set from the terminal width below), so
# the CPU chart gives every core an equal width. ▰ sits inside its cell, unlike a
# block, so segments stay apart from each other and from the bar on the next row.
BW=14
# Each bar is built as cells, CH (glyph) and FG (color), so its number can then
# replace the cells in the middle.
# bar NUM DEN COLOR -> cells, in whole segments.
bar() {
  local num=$1 den=$2 col=$3 i fill
  [ "$den" -gt 0 ] || den=1
  fill=$(( (num * BW + den / 2) / den )); [ "$fill" -gt "$BW" ] && fill=$BW
  # A sliver of use still shows one segment.
  [ "$num" -gt 0 ] && [ "$fill" -eq 0 ] && fill=1
  CH=(); FG=()
  for (( i = 0; i < BW; i++ )); do
    if   [ "$i" -lt "$fill" ]; then CH[i]='▰'; FG[i]=$col
    else CH[i]='▱'; FG[i]=$EMPTY; fi
  done
}
# finish_bar TEXT COLOR [PAST_LIMIT] -> BP/BC: the cells with the number in the
# middle. Every bar cuts the same slot, a box's width, and centers the number
# in it (an odd space goes after), so 9% and 100% take
# the same room and a box is always the same size.
finish_bar() {
  local t=$1 col=$2 x=$3 w=4 span st i lp rp tp tc
  [ ${#t} -gt "$w" ] && w=${#t}
  span=$(( w + 4 )); lp=$(spaces $(( (w - ${#t}) / 2 ))); rp=$(spaces $(( (w - ${#t} + 1) / 2 )))
  if [ -n "$x" ]; then
    tp="▕ ${lp}${t}${rp} ▏"; tc="${BAD}${BOX}▕ ${R}${CRIT}${BOX}${lp}${t}${rp}${R}${BAD}${BOX} ▏${R}"
  else
    tp="  ${lp}${t}${rp}  "; tc="  ${lp}${col}${t}${R}${rp}  "
  fi
  st=$(( (BW - span) / 2 )); [ "$st" -lt 0 ] && st=0
  # A space inside each edge keeps the bar off its frame.
  BP="▕ "; BC="${DIM}▕${R} "
  for (( i = 0; i < BW; i++ )); do
    if [ "$i" -lt "$st" ] || [ "$i" -ge $(( st + span )) ]; then
      BP="${BP}${CH[i]}"; BC="${BC}${FG[i]}${CH[i]}${R}"
    elif [ "$i" -eq "$st" ]; then
      BP="${BP}${tp}"; BC="${BC}${tc}"
    fi
  done
  BP="${BP} ▏ "; BC="${BC} ${DIM}▏${R} "
}
sevc() { if [ "$1" -ge "$3" ]; then printf '%s' "$BAR_BAD"; elif [ "$1" -ge "$2" ]; then printf '%s' "$BAR_WARN"; else printf '%s' "$BAR_OK"; fi; }
row_label() { ap "$1" "$(printf '%-7s' "$2:")" "${LAB}$2${R}${DOT}:${R}$(spaces $(( 6 - ${#2} )))"; }

# --- The machine and Claude's activity ---
# CPU, memory, swap and network come from macOS itself. Temperature needs iSMC (brew tap
# dkorunic/tap && brew install ismc), which reads the sensors without sudo; when
# it's missing the Temp slot says so rather than failing the whole status line.
ncpu=$(sysctl -n hw.ncpu 2>/dev/null); [ "${ncpu:-0}" -gt 0 ] 2>/dev/null || ncpu=1
# One reading of the machine is shared by every session for 10 s, so they all
# show the same numbers. The first session past that takes the next reading.
machine="$HOME/.claude/cache/machine-v2"   # cpu, mem, cores, swap, net in, net out
mage=999999; [ -f "$machine" ] && mage=$(( now - $(stat -f %m "$machine" 2>/dev/null || echo 0) ))
cores=""
if [ "$mage" -lt 10 ]; then
  IFS=$'\t' read -r cpu_pct mem_pct cores swap_mb rx_bps tx_bps < "$machine"
else
# Per-core usage comes straight from the kernel's tick counters (host_processor_info),
# as the change since the previous reading, about 10 s earlier. macOS has no
# command for it, so the system Python reads it through ctypes.
if command -v python3 >/dev/null 2>&1; then
  cores=$(python3 -I - "$HOME/.claude/cache/cpu-ticks" 2>/dev/null <<'PY'
import ctypes, ctypes.util, sys, os
libc = ctypes.CDLL(ctypes.util.find_library("c"))
n = ctypes.c_uint(); info = ctypes.POINTER(ctypes.c_int)(); cnt = ctypes.c_uint()
libc.mach_host_self.restype = ctypes.c_uint
if libc.host_processor_info(libc.mach_host_self(), 2, ctypes.byref(n), ctypes.byref(info), ctypes.byref(cnt)) != 0:
    sys.exit(1)
now = [[info[i * 4 + j] & 0xFFFFFFFF for j in range(4)] for i in range(n.value)]  # user, system, idle, nice
path = sys.argv[1]
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    prev = [[int(x) for x in l.split()] for l in open(path)]
except Exception:
    prev = []
if len(prev) != len(now):
    prev = [[0, 0, 0, 0] for _ in now]
out = []
for a, b in zip(now, prev):
    d = [(x - y) % 2**32 for x, y in zip(a, b)]
    tot = sum(d)
    out.append(round(100 * (tot - d[2]) / tot) if tot else 0)
tmp = path + ".%d" % os.getpid()
with open(tmp, "w") as f:
    f.write("\n".join(" ".join(map(str, c)) for c in now))
os.replace(tmp, path)
print(" ".join(map(str, out)))
PY
)
fi
if [ -n "$cores" ]; then
  cpu_pct=$(printf '%s\n' "$cores" | awk '{ for (i = 1; i <= NF; i++) s += $i; printf "%d", s / NF + 0.5 }')
else
  # Without Python: ps reports each process's recent share of one core.
  cpu_pct=$(ps -A -o %cpu= | awk -v n="$ncpu" '{ s += $1 } END { v = int(s / n + 0.5); print (v > 100 ? 100 : v) }')
fi
# The kernel's memorystatus level is the share of memory it counts as free.
mem_free=$(sysctl -n kern.memorystatus_level 2>/dev/null); mem_pct=$(( 100 - ${mem_free:-100} ))
# Swap in use, in MB. macOS grows the swap file as it needs, so the amount used
# says more about memory pressure than a share of the file would.
swap_mb=$(sysctl -n vm.swapusage 2>/dev/null | awk '{ for (i = 1; i < NF; i++) if ($i == "used") { v = $(i + 2); sub(/M$/, "", v); printf "%d", v } }')
# Network: bytes in and out across the en* interfaces (Wi-Fi, Ethernet), as the
# rate since the previous reading. Loopback and VPN tunnels are left out, since
# their traffic also crosses a real interface and would be counted twice.
mkdir -p "${machine%/*}"
netc="$HOME/.claude/cache/net-bytes"
read -r rx tx <<EOF
$(netstat -ibn 2>/dev/null | awk '$1 ~ /^en[0-9]+$/ && $3 ~ /^<Link/ { i += $(NF - 4); o += $(NF - 1) } END { printf "%.0f %.0f", i, o }')
EOF
rx_bps=0; tx_bps=0
if [ -f "$netc" ] && read -r pt prx ptx < "$netc" && [ "$now" -gt "${pt:-0}" ]; then
  rx_bps=$(awk -v a="$rx" -v b="$prx" -v t=$(( now - pt )) 'BEGIN { d = a - b; printf "%.0f", (d > 0 ? d / t : 0) }')
  tx_bps=$(awk -v a="$tx" -v b="$ptx" -v t=$(( now - pt )) 'BEGIN { d = a - b; printf "%.0f", (d > 0 ? d / t : 0) }')
fi
printf '%s %s %s\n' "$now" "${rx:-0}" "${tx:-0}" > "$netc.$$" && mv -f "$netc.$$" "$netc"
printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$cpu_pct" "$mem_pct" "$cores" "${swap_mb:-0}" "$rx_bps" "$tx_bps" > "$machine.$$" && mv -f "$machine.$$" "$machine"
fi
: "${cpu_pct:=0}" "${mem_pct:=0}" "${swap_mb:=0}" "${rx_bps:=0}" "${tx_bps:=0}"
have_ismc=0; command -v ismc >/dev/null 2>&1 && have_ismc=1
# iSMC takes about a second to read the temperatures, so it runs in the
# background every 10 s and leaves its reading in a cache, like the Fable limit.
cpu_temp=""
if [ "$have_ismc" = 1 ]; then
  sensors="$HOME/.claude/cache/sensors.json"; sstamp="$HOME/.claude/cache/sensors.stamp"
  sage=999999; [ -f "$sstamp" ] && sage=$(( now - $(stat -f %m "$sstamp" 2>/dev/null || echo 0) ))
  if [ "$sage" -ge 10 ]; then
    mkdir -p "${sstamp%/*}"; touch "$sstamp"
    (
      ismc temp -o json 2>/dev/null | jq -c '{temp: (."CPU Die Average".quantity // null)}' > "$sensors.$$" && mv -f "$sensors.$$" "$sensors"
    ) >/dev/null 2>&1 &
  fi
  if [ -f "$sensors" ] && [ $(( now - $(stat -f %m "$sensors" 2>/dev/null || echo 0) )) -lt 60 ]; then
    cpu_temp=$(jq -r '.temp // "" | if . == "" then "" else round end' "$sensors" 2>/dev/null)
  fi
fi

# Turns: each prompt you send gets its own promptId in the transcript. A long
# session's transcript runs to tens of MB and a full scan costs ~0.2 s, so the
# count is kept per session and only the bytes added since the last run are read.
turns=0
if [ -f "$tpath" ]; then
  tc="$HOME/.claude/cache/turns-${sid}"
  size=$(stat -f %z "$tpath" 2>/dev/null || echo 0)
  off=0; cnt=0; last=""
  [ -f "$tc" ] && read -r off cnt last < "$tc"
  [ "${size:-0}" -lt "${off:-0}" ] 2>/dev/null && { off=0; cnt=0; last=""; }
  if [ "$size" -gt "$off" ] 2>/dev/null; then
    read -r add last <<EOF
$(tail -c +$(( off + 1 )) "$tpath" | grep -o '"promptId":"[^"]*"' | awk -v prev="$last" '
  $0 != prev && !seen[$0]++ { n++ } { l = $0 } END { print n + 0, (l == "" ? prev : l) }')
EOF
    cnt=$(( cnt + ${add:-0} ))
    mkdir -p "${tc%/*}"; printf '%s %s %s\n' "$size" "$cnt" "$last" > "$tc"
  fi
  turns=$cnt
fi

has_fable=0; [ -n "$fable_pct" ] && has_fable=1

# The left rows are built by a function, because the bar width depends on how
# much room the right side leaves, which is only known once it is built.
build_left() {
  LP=(); LC=()
  # Left rows: 0 ctx, 1 5h, 2 7d, 3 fable; 4 is the machine, printed above them.
  # Each row's number sits in the middle of its bar.
  val "$ac_pct"
  [ "${ctx_tok:-0}" -gt 250000 ] 2>/dev/null && VX=1
  row_label 0 Ctx
  bar "$ctx_tok" "$win" "$(sevc "$ac_pct" 50 80)"
  finish_bar "${ctxk}k" "$VK" "$VX"; ap 0 "$BP" "$BC"
  row_label 1 5h; val "$five_pct"
  bar "$five_pct" 100 "$(sevc "$five_pct" 50 80)"; finish_bar "$VR" "$VK" "$VX"; ap 1 "$BP" "$BC"
  row_label 2 7d; val "$seven_pct"
  bar "$seven_pct" 100 "$(sevc "$seven_pct" 50 80)"; finish_bar "$VR" "$VK" "$VX"; ap 2 "$BP" "$BC"
  if [ "$has_fable" = 1 ]; then
    row_label 3 Fable; val "$fable_pct"
    bar "$fable_pct" 100 "$(sevc "$fable_pct" 50 80)"; finish_bar "$VR" "$VK" "$VX"; ap 3 "$BP" "$BC"
  fi
  row_label 4 CPU; val "$cpu_pct"
  if [ -n "$cores" ]; then core_chart; else bar "$cpu_pct" 100 "$(sevc "$cpu_pct" 50 80)"; fi
  finish_bar "$VR" "$VK" "$VX"; ap 4 "$BP" "$BC"

  # "Resets" is written once, on the 5h row; the weekly times hang off it tree-style,
  # the stem dropping from the middle of the word, the times lined up under 1h49m.
  ap 1 "Resets: ${five_r}" "${LAB}Resets${R}${DOT}:${R} ${VAL}${five_r}${R}"
  if [ "$has_fable" = 1 ]; then
    ap 2 "  ├──── ${seven_r}" "  ${LAB}├────${R} ${VAL}${seven_r}${R}"
    ap 3 "  └──── ${fable_r}" "  ${LAB}└────${R} ${VAL}${fable_r}${R}"
  else
    ap 2 "  └──── ${seven_r}" "  ${LAB}└────${R} ${VAL}${seven_r}${R}"
    LP[3]=""; LC[3]=""
  fi
  # AC · Win and Mem · Swap form a grid: labels pad to the widest in their
  # column, values too, and when either value in a column is boxed the other
  # gets blank cells where the box's edges go, so the numbers line up.
  val "$ac_pct";  a1=$VR; k1=$VK; x1=$VX
  val "$win_pct"; a2=$VR; k2=$VK; x2=$VX
  val "$mem_pct"; m1=$VR; n1=$VK; y1=$VX
  # Swap steps up from 1 GB and is past its limit from 8 GB.
  if [ "$swap_mb" -ge 1024 ]; then m2="$(( (swap_mb + 512) / 1024 ))G"; else m2="${swap_mb}M"; fi
  [ "$swap_mb" -eq 0 ] && m2=0
  y2=""; n2=$OK; [ "$swap_mb" -ge 1024 ] && n2=$WARN; [ "$swap_mb" -ge 8192 ] && { n2=$CRIT; y2=1; }
  local w1=${#a1} w2=${#a2} b1="" b2=""
  [ ${#m1} -gt "$w1" ] && w1=${#m1}; [ ${#m2} -gt "$w2" ] && w2=${#m2}
  [ -n "$x1$y1" ] && b1=1; [ -n "$x2$y2" ] && b2=1
  grid_row 0 AC Win "$a1" "$k1" "$x1" "$a2" "$k2" "$x2"
  grid_row 4 Mem Swap "$m1" "$n1" "$y1" "$m2" "$n2" "$y2"
}
# cell TEXT COLOR PAST_LIMIT WIDTH COLUMN_BOXED LAST -> CP_/CC_: one grid value.
cell() {
  local pad; pad=$(spaces $(( $4 - ${#1} ))); [ -n "$6" ] && pad=""
  if [ -n "$3" ]; then
    CP_="▕ $1$pad ▏"; CC_="${BAD}${BOX}▕ ${R}${CRIT}${BOX}$1$pad${R}${BAD}${BOX} ▏${R}"
  elif [ -n "$5" ]; then
    CP_="  $1$pad"; CC_="  $2$1${R}$pad"; [ -z "$6" ] && { CP_="$CP_  "; CC_="$CC_  "; }
  else CP_="$1$pad"; CC_="$2$1${R}$pad"; fi
}
# grid_row ROW LABEL1 LABEL2 TEXT1 COLOR1 PAST1 TEXT2 COLOR2 PAST2, using w1/w2/b1/b2.
# In a boxed column the box's edge stands in for the space after the label: the
# edge is drawn at the right of its cell, so a space before it would look doubled.
grid_row() {
  local p c s1=" " s2=" "
  [ -n "$b1" ] && s1=""; [ -n "$b2" ] && s2=""
  p="$(printf '%-4s' "$2:")$s1"; c="${LAB}$2${R}${DOT}:${R}$(spaces $(( 3 - ${#2} )))$s1"
  cell "$4" "$5" "$6" "$w1" "$b1"; p="$p$CP_ · "; c="$c$CC_${DOT} · ${R}"
  p="$p$(printf '%-5s' "$3:")$s2"; c="$c${LAB}$3${R}${DOT}:${R}$(spaces $(( 4 - ${#3} )))$s2"
  cell "$7" "$8" "$9" "$w2" "$b2" last; p="$p$CP_"; c="$c$CC_"
  ap "$1" "$p" "$c"
}

# With per-core numbers, the CPU's bar becomes a chart: each core a column that
# rises with its load, stretched across the bar's width and colored like a bar.
SPARK=(▁ ▂ ▃ ▄ ▅ ▆ ▇ █)
core_chart() {
  local -a c=($cores); local n=${#c[@]} j p
  CH=(); FG=()
  for (( j = 0; j < BW; j++ )); do
    p=${c[$(( j * n / BW ))]}
    CH[j]=${SPARK[$(( p >= 100 ? 7 : p * 8 / 100 ))]}
    if [ "$p" -ge 80 ]; then FG[j]=$BAR_BAD; elif [ "$p" -ge 50 ]; then FG[j]=$BAR_WARN; else FG[j]=$BAR_OK; fi
  done
}

# --- Right rows: a mauve label, a bright part, then a slate teal detail ---
# Long paths keep the first two folders and the last one: ~/.claude/tmp/…/scratchpad.
short_dir() {
  local p=$1 n
  [ ${#p} -le 32 ] && { printf '%s' "$p"; return; }
  IFS=/ read -r -a parts <<< "$p"; n=${#parts[@]}
  [ "$n" -le 4 ] && { printf '%s' "$p"; return; }
  printf '%s' "${parts[0]}/${parts[1]}/${parts[2]}/…/${parts[$(( n - 1 ))]}"
}
sdir=$(short_dir "$dir")
# Branch names stop at 20 characters so one long name can't push the grey column away.
[ ${#branch} -gt 20 ] && branch="${branch:0:19}…"
sid8="${sid:0:8}"

# The prompt cache shows how much of its life (5m or 1h) has gone: it fills toward
# trouble like every other percentage, and at 100% the next message pays to
# rebuild the whole context. Hidden until a response has reported caching.
cache_pct=""
if [ "$cwarm" = false ]; then cache_pct=100
elif [ "$cwarm" = true ] && [ "$cexp" -gt 0 ] 2>/dev/null; then
  case "$cttl" in 5m) ttl=300 ;; *) ttl=3600 ;; esac
  cache_pct=$(( ( (ttl - (cexp - now)) * 100 + ttl / 2 ) / ttl ))
  [ "$cache_pct" -lt 0 ] && cache_pct=0; [ "$cache_pct" -gt 100 ] && cache_pct=100
fi

BRP=(); BRC=(); GRP=(); GRC=(); GKP=(); GKC=()   # bright and detail parts per right row
# The cache is the model row's detail: the label is teal like the other details,
# but the number keeps its limit color so an expired cache still stands out.
# Effort takes the colors of Claude Code's /effort picker. Its animations tick
# every 100 ms; a status line only redraws on events and the refresh timer, so
# xhigh's highlight steps a letter per redraw. Max's rainbow holds still, spread
# end to end across the word, because stepping it popped instead of flowing.
E=$'\033'; RGB() { printf '%s[38;2;%s;%s;%sm' "$E" "$1" "$2" "$3"; }
RAINBOW=("$(RGB 235 95 87)" "$(RGB 245 139 87)" "$(RGB 250 195 95)" "$(RGB 145 200 130)" \
         "$(RGB 130 170 220)" "$(RGB 155 130 200)" "$(RGB 200 130 180)")
ULTRA=$(RGB 175 135 255)   # xhigh's base purple, the CLI's autoAccept
effort_colored() {
  local w=$1 n=${#1} i p out=""
  case "$lvl" in
    low)    printf '%s%s%s' "$(RGB 255 193 7)" "$w" "$R" ;;
    medium) printf '%s%s%s' "$(RGB 78 186 101)" "$w" "$R" ;;
    high)   printf '%s%s%s' "$(RGB 177 185 249)" "$w" "$R" ;;
    xhigh)
      p=$(( now % (n + 4) - 2 ))
      for (( i = 0; i < n; i++ )); do
        if   [ "$i" -eq "$p" ]; then out="${out}${E}[1m$(RGB 208 180 255)${w:i:1}${R}"
        elif [ $(( i - p )) -eq 1 ] || [ $(( p - i )) -eq 1 ]; then out="${out}${E}[1m${ULTRA}${w:i:1}${R}"
        else out="${out}${ULTRA}${w:i:1}${R}"; fi
      done
      printf '%s' "$out" ;;
    max)
      for (( i = 0; i < n; i++ )); do
        out="${out}${E}[1m${RAINBOW[$(( n > 1 ? i * 6 / (n - 1) : 0 ))]}${w:i:1}${R}"
      done
      printf '%s' "$out" ;;
    *) printf '%s%s%s' "$VAL" "$w" "$R" ;;
  esac
}
BRP[0]="${model}/${effort}"; BRC[0]="${VAL}${model}${R}${BAR_WARN}/${R}$(effort_colored "$effort")"
GRP[0]=""; GRC[0]=""
if [ -n "$cache_pct" ]; then
  val "$cache_pct"
  GRP[0]="Cache: ${VP}"; GRC[0]="${DET}Cache${R}${DOT}:${R} ${VC}"
fi

if [ "$in_git" = 1 ]; then
  RL1=Git
  BRP[1]="$branch"; BRC[1]="${VAL}${branch}${R}"
  [ "${ahead:-0}"  -gt 0 ] && { BRP[1]="${BRP[1]} ↑${ahead}";  BRC[1]="${BRC[1]} ${OK}↑${ahead}${R}"; }
  [ "${behind:-0}" -gt 0 ] && { BRP[1]="${BRP[1]} ↓${behind}"; BRC[1]="${BRC[1]} ${BAD}↓${behind}${R}"; }
  if [ "${dirty:-0}" -gt 0 ]; then BRP[1]="${BRP[1]} ✚${dirty}"; BRC[1]="${BRC[1]} ${WARN}✚${dirty}${R}"
  else BRP[1]="${BRP[1]} ✓"; BRC[1]="${BRC[1]} ${OK}✓${R}"; fi
  GRP[1]="$sdir"; GRC[1]="${DET}${sdir}${R}"
else
  # Outside a repo the folder is the row's only item, so it stays bright.
  RL1=Dir
  BRP[1]="$sdir"; BRC[1]="${VAL}${sdir}${R}"; GRP[1]=""; GRC[1]=""
fi
BRP[2]="$kube"; BRC[2]="${VAL}${kube}${R}"; GRP[2]="$ns"; GRC[2]="${DET}${ns}${R}"
# The session's name goes last: it is the one part that can run long, so it is
# what gets shortened when the row runs out of room. GKP/GKC keep the colored
# part before it, so shortening the name doesn't wash out the cost and turn.
BRP[3]="$sid8"; BRC[3]="${VAL}${sid8}${R}"
graded "${sc%.*}" 50 100 "\$${sc}"; CSP=$GP_; CSC=$GC_
graded "$turns" 150 300 "$turns"; TNP=$GP_; TNC=$GC_
GKP[3]="${CSP} · Turn: ${TNP}"; GKC[3]="${CSC}${DOT} · ${R}${DET}Turn${R}${DOT}:${R} ${TNC}"
GRP[3]="${GKP[3]}"; GRC[3]="${GKC[3]}"
if [ -n "$sname" ]; then
  GRP[3]="${GRP[3]} · ${sname}"; GRC[3]="${GRC[3]}${DOT} · ${R}${DET}${sname}${R}"
fi
# The machine row's right side: the network, then CPU temperature as its detail.
# Temperature keeps its limit color there, like the cache on the model row.
# rate BYTES_PER_S -> a short rate, right-aligned in 8 columns (840 B/s, 12 KB/s,
# 1.2 MB/s), so the details after it don't shift as the numbers change.
rate() { awk -v b="$1" 'BEGIN { split("B KB MB GB", u); i = 1; while (b >= 999.5 && i < 4) { b /= 1000; i++ }
  n = (b < 9.95 && i > 1) ? sprintf("%.1f", b) : sprintf("%d", b + 0.5)
  printf "%8s", n " " u[i] "/s" }'; }
# The arrows stay white; only the rate takes its color. Each rate is right-
# aligned in its 8 columns, so its unit always ends in the same place.
graded "$rx_bps" 1000000 10000000 "$(rate "$rx_bps")" nobox; NIP=$GP_; NIC=$GC_
graded "$tx_bps" 1000000 10000000 "$(rate "$tx_bps")" nobox; NOP=$GP_; NOC=$GC_
BRP[4]="↓${NIP} ↑${NOP}"; BRC[4]="${VAL}↓${R}${NIC} ${VAL}↑${R}${NOC}"
if [ "$have_ismc" = 0 ]; then
  GRP[4]="iSMC not available"; GRC[4]="${DET}iSMC not available${R}"
else
  if   [ -z "$cpu_temp" ]; then TMP="-"; TMC="${DET}-${R}"
  elif [ "$cpu_temp" -ge 85 ]; then boxed "${cpu_temp}°"; TMP=$CP_; TMC=$CC_
  elif [ "$cpu_temp" -ge 70 ]; then TMP="${cpu_temp}°"; TMC="${WARN}${cpu_temp}°${R}"
  else TMP="${cpu_temp}°"; TMC="${OK}${cpu_temp}°${R}"; fi
  GRP[4]="Temp: ${TMP}"; GRC[4]="${DET}Temp${R}${DOT}:${R} ${TMC}"
fi
RLAB=(Model "$RL1" K8s Session Net)

# The details start in one column: pad each bright part to the widest one that
# has a detail after it.
MW=0
# A short terminal (under 20 rows, from LINES) leaves out the machine row, so
# the status line takes four rows instead of five. Everything below measures
# and prints only the rows in ROWS, in the order they print.
ROWS="4 0 1 2 3"
[ "${LINES:-0}" -gt 0 ] 2>/dev/null && [ "$LINES" -lt 20 ] && ROWS="0 1 2 3"
for i in $ROWS; do [ -n "${GRP[$i]}" ] && [ ${#BRP[$i]} -gt "$MW" ] && MW=${#BRP[$i]}; done

# --- Width ---
# Claude Code passes the terminal's width in COLUMNS and keeps a few columns for
# its own padding. The right side keeps its natural width; the bars take what is
# left, in whole characters per core (1 to 4), and the values column keeps at
# most 3 spare. On a narrower terminal the bars win over the teal details: they
# hold at two characters per core while the details shorten, then drop. Then
# the bars go to one per core, and last the whole right side drops.
cols=${COLUMNS:-145}; [ "$cols" -gt 0 ] 2>/dev/null || cols=145
W=$(( cols - 5 ))
BW=$ncpu; build_left
Bmin=0; CB=0; CF=0
for i in $ROWS; do
  b=$(( ${#LP[$i]} - BW - 12 )); [ "$b" -gt "$Bmin" ] && Bmin=$b
  b=${#BRP[$i]}; [ "$b" -gt "$CB" ] && CB=$b
  [ -n "${GRP[$i]}" ] && b=$(( MW + 2 + ${#GRP[$i]} )); [ "$b" -gt "$CF" ] && CF=$b
done
CB=$(( CB + 9 )); CF=$(( CF + 9 ))
# The left side with the bars at one and two characters per core, values unpadded.
L1=$(( ncpu + 12 + Bmin )); L2=$(( 2 * ncpu + 12 + Bmin ))
pmax=4
if   [ $(( L2 + 3 + CF )) -le "$W" ]; then show=full; C=$CF
elif [ $(( L2 + 3 + 9 + MW + 2 + 16 )) -le "$W" ]; then
  # The details get whatever the right side has left; a long one ends in …,
  # in plain teal, since its colors can't be cut part way through. Cache and
  # Temp are single values, so they drop out whole rather than lose digits.
  show=full; pmax=2; C=$(( W - L2 - 3 )); room=$(( C - 9 - MW - 2 ))
  for i in $ROWS; do
    if [ ${#GRP[$i]} -gt "$room" ]; then
      k=${GKP[$i]}
      if [ "$i" = 0 ] || [ "$i" = 4 ]; then GRP[$i]=""; GRC[$i]=""
      elif [ -n "$k" ] && [ "$room" -gt $(( ${#k} + 4 )) ]; then
        t=${GRP[$i]:${#k}}; t="${t:0:$(( room - ${#k} - 1 ))}…"
        GRP[$i]="${k}${t}"; GRC[$i]="${GKC[$i]}${DET}${t}${R}"
      elif [ -n "$k" ] && [ "$room" -ge "${#k}" ]; then
        GRP[$i]=$k; GRC[$i]=${GKC[$i]}
      else
        GRP[$i]="${GRP[$i]:0:$(( room - 1 ))}…"; GRC[$i]="${DET}${GRP[$i]}${R}"
      fi
    fi
  done
elif [ $(( L2 + 3 + CB )) -le "$W" ]; then show=bright; pmax=4; C=$CB
elif [ $(( L1 + 3 + CB )) -le "$W" ]; then show=bright; pmax=2; C=$CB
else show=left; pmax=4; C=0; fi
avail=$W; [ "$show" != left ] && avail=$(( W - 3 - C ))
per=$pmax
while [ "$per" -gt 1 ] && [ $(( per * ncpu + 12 + Bmin )) -gt "$avail" ]; do per=$(( per - 1 )); done
BW=$(( per * ncpu ))
# The bars then take every spare column, up to four per core, so no width
# leaves a gap at the end of the line. The CPU chart gives some cores one more
# column than others, spread evenly, when the width isn't a multiple of 14.
b=$(( avail - 12 - Bmin )); [ "$b" -gt $(( pmax * ncpu )) ] && b=$(( pmax * ncpu ))
[ "$b" -gt "$BW" ] && BW=$b
build_left
# The values column pads out to the divider by 3 spare columns at most; any
# other leftover goes at the end of the line, where empty space doesn't show.
A=$(( BW + 12 ))
L=$avail; [ $(( A + Bmin + 3 )) -lt "$L" ] && L=$(( A + Bmin + 3 ))
[ "$show" = left ] && L=0
for i in $ROWS; do [ ${#LP[$i]} -gt "$L" ] && L=${#LP[$i]}; done
n=0
for i in $ROWS; do
  [ "$n" -gt 0 ] && printf '\n'; n=$(( n + 1 ))
  if [ "$show" = left ]; then printf '%s' "${LC[$i]}"; continue; fi
  printf '%s%s' "${LC[$i]}" "$(spaces $(( L - ${#LP[$i]} )))"
  printf '%s' "${DIV} │ ${R}${LAB}${RLAB[$i]}${R}${DOT}:${R}$(spaces $(( 8 - ${#RLAB[$i]} )))${BRC[$i]}"
  if [ "$show" = full ] && [ -n "${GRP[$i]}" ]; then
    printf '%s%s' "$(spaces $(( MW - ${#BRP[$i]} + 2 )))" "${GRC[$i]}"
  fi
done
exit 0
