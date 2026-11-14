#!/usr/bin/env bash
# Claude Code status line. Reads session-context JSON on stdin and prints four
# rows: a bar for context and each usage limit on the left, and what the session
# is working with on the right. Wired via ~/.claude/settings.json as
# `bash ~/.claude/statusline.sh`.
#
#   Ctx   ▕▰▰▰▰▰▱▱▱▱▱▱▱┃▱▱▱▱▱▱▱▱▱▱▱▱▏ 191k  AC 39% · Win 19% │ Model   Opus 5.5/High  Cache 8%
#   5h    ▕▰▰▰▰▰▰▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▏ 37%   Resets 1h49m     │ Git     main ↓7 ✚2     ~/git/personal/bluebird
#   7d    ▕▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱▱▱▱▏ 81%ꜝ    ├─── 3d4h      │ K8s     admin@stable   default
#   Fable ▕▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▏ 100%ꜝ   └─── 3d4h      │ Session $3.63          1feba53f · claude-80
#
# The ctx bar spans the model's whole window. ┃ marks where auto-compact fires,
# and the dusty rose cells before it are the last quarter of the way there. AC is
# the share of that compaction point used, Win the share of the whole window.
# With auto-compact on, Win can never pass the AC point, so it only matters when
# compaction is off (DISABLE_AUTO_COMPACT=1). The Fable row is hidden until the
# Fable limit has been fetched (see below). The Git row reads Dir outside a
# repo; ↑/↓ track the branch's own upstream, ✚ counts changed files. Cache is how
# much of the prompt cache's life has gone since the last message.
#
# One color per job: mauve labels a value, white is a value, slate teal is the
# minor detail that ends a row, lavender dots sit between items, icy blue draws
# the dividers and the compaction mark, and mint / gold / coral is a value with a
# limit: mint under 50%, gold under 80%, and bold coral with a raised ꜝ at 80%
# and up (AC from 75%, the token count past 250K). The bars step sooner, by thirds:
# steel blue under 33%, soft violet under 66%, orchid from 66% (ctx by its AC).
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
CRIT=$'\033[1;38;5;210m'   # bold coral: a value past its limit, then a raised ꜝ in plain coral
EMPTY=$'\033[38;5;237m'; ZONE=$'\033[38;5;95m'; R=$'\033[0m'

# Each row is built twice: P* holds the plain text (for measuring) and C* the
# colored text (for printing). ap ROW PLAIN COLORED appends to one left row.
LP=(); LC=(); RP=(); RC=()
ap() { LP[$1]="${LP[$1]}$2"; LC[$1]="${LC[$1]}$3"; }
spaces() { [ "$1" -gt 0 ] && printf '%*s' "$1" ''; }

# val VALUE [WARN=50] [CRIT=80] -> VP/VC.
val() {
  local w=${2:-50} c=${3:-80}
  if   [ "$1" -ge "$c" ]; then VP="$1%ꜝ"; VC="${CRIT}$1%${R}${BAD}ꜝ${R}"
  elif [ "$1" -ge "$w" ]; then VP="$1%";  VC="${WARN}$1%${R}"
  else                         VP="$1%";  VC="${OK}$1%${R}"; fi
}

# --- Bars ---
# 25 segments of 4%. ▰ sits inside its cell, unlike a block, so segments stay
# apart from each other and from the bar on the next row.
BW=25
# bar NUM DEN COLOR [MARK_COL] [ZONE_START] -> BP/BC, in whole segments.
bar() {
  local num=$1 den=$2 col=$3 mk=${4:--1} zs=${5:--1} i fill s
  [ "$den" -gt 0 ] || den=1
  fill=$(( (num * BW + den / 2) / den )); [ "$fill" -gt "$BW" ] && fill=$BW
  # A sliver of use still shows one segment.
  [ "$num" -gt 0 ] && [ "$fill" -eq 0 ] && fill=1
  BP="▕"; BC="${DIM}▕${R}"
  for (( i = 0; i < BW; i++ )); do
    if   [ "$i" -lt "$fill" ]; then s='▰'; BC="${BC}${col}${s}"
    elif [ "$i" -eq "$mk" ]; then s='┃'; BC="${BC}${DIV}${s}"
    elif [ "$zs" -ge 0 ] && [ "$i" -ge "$zs" ] && [ "$i" -lt "$mk" ]; then s='▱'; BC="${BC}${ZONE}${s}"
    else s='▱'; BC="${BC}${EMPTY}${s}"; fi
    BP="${BP}${s}"
  done
  # Grey edges hold the bar, so it needs no divider before its value.
  BP="${BP}▏ "; BC="${BC}${R}${DIM}▏${R} "
}
sevc() { if [ "$1" -ge "$3" ]; then printf '%s' "$BAR_BAD"; elif [ "$1" -ge "$2" ]; then printf '%s' "$BAR_WARN"; else printf '%s' "$BAR_OK"; fi; }
row_label() { ap "$1" "$(printf '%-6s' "$2")" "${LAB}$(printf '%-6s' "$2")${R}"; }

has_fable=0; [ -n "$fable_pct" ] && has_fable=1

# Left rows: 0 ctx, 1 5h, 2 7d, 3 fable.
row_label 0 Ctx
bar "$ctx_tok" "$win" "$(sevc "$ac_pct" 33 66)" $(( ac_thr * BW / win )) $(( ac_thr * 3 / 4 * BW / win )); ap 0 "$BP" "$BC"
row_label 1 5h;  bar "$five_pct" 100 "$(sevc "$five_pct" 33 66)";   ap 1 "$BP" "$BC"
row_label 2 7d;  bar "$seven_pct" 100 "$(sevc "$seven_pct" 33 66)"; ap 2 "$BP" "$BC"
[ "$has_fable" = 1 ] && { row_label 3 Fable; bar "$fable_pct" 100 "$(sevc "$fable_pct" 33 66)"; ap 3 "$BP" "$BC"; }

# The first value on each row is padded so the words after them form one column.
if [ "${ctx_tok:-0}" -gt 250000 ] 2>/dev/null; then
  TP="${ctxk}kꜝ"; TC="${CRIT}${ctxk}k${R}${BAD}ꜝ${R}"
else TP="${ctxk}k"; TC="${VAL}${ctxk}k${R}"; fi
val "$five_pct";  HP=$VP; HC=$VC
val "$seven_pct"; SP=$VP; SC=$VC
FP=""; [ "$has_fable" = 1 ] && { val "$fable_pct"; FP=$VP; FC=$VC; }
FW=0
for v in "$TP" "$HP" "$SP" "$FP"; do [ ${#v} -gt "$FW" ] && FW=${#v}; done
FW=$(( FW + 1 ))
first() { ap "$1" "$2$(spaces $(( FW - ${#2} )))" "$3$(spaces $(( FW - ${#2} )))"; }

val "$ac_pct" 50 75; ACP=$VP; ACC=$VC
val "$win_pct";      WNP=$VP; WNC=$VC
first 0 "$TP" "$TC"
ap 0 "AC ${ACP} · Win ${WNP}" "${LAB}AC${R} ${ACC}${DOT} · ${R}${LAB}Win${R} ${WNC}"
# "Resets" is written once, on the 5h row; the weekly times hang off it tree-style,
# the stem dropping from the middle of the word, the times lined up under 1h49m.
first 1 "$HP" "$HC"
ap 1 "Resets ${five_r}" "${LAB}Resets${R} ${VAL}${five_r}${R}"
first 2 "$SP" "$SC"
if [ "$has_fable" = 1 ]; then
  ap 2 "  ├─── ${seven_r}" "  ${LAB}├───${R} ${VAL}${seven_r}${R}"
  first 3 "$FP" "$FC"
  ap 3 "  └─── ${fable_r}" "  ${LAB}└───${R} ${VAL}${fable_r}${R}"
else
  ap 2 "  └─── ${seven_r}" "  ${LAB}└───${R} ${VAL}${seven_r}${R}"
  LP[3]=""; LC[3]=""
fi

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

BRP=(); BRC=(); GRP=(); GRC=()   # bright and detail parts per right row
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
  GRP[0]="Cache ${VP}"; GRC[0]="${DET}Cache${R} ${VC}"
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
if [ -n "$sname" ]; then
  BRP[3]="\$${sc}"; BRC[3]="${VAL}\$${sc}${R}"
  GRP[3]="$sid8 · $sname"; GRC[3]="${DET}${sid8}${R}${DOT} · ${R}${DET}${sname}${R}"
else
  BRP[3]="\$${sc}"; BRC[3]="${VAL}\$${sc}${R}"; GRP[3]="$sid8"; GRC[3]="${DET}${sid8}${R}"
fi
RLAB=(Model "$RL1" K8s Session)

# The details start in one column: pad each bright part to the widest one that
# has a detail after it.
MW=0
for i in 0 1 2 3; do [ -n "${GRP[$i]}" ] && [ ${#BRP[$i]} -gt "$MW" ] && MW=${#BRP[$i]}; done

# --- Hardware: a fourth column ---
# Only what macOS reports without sudo or extra tools. Temperature and fan speed
# need powermetrics (root) or a third-party SMC reader, so the Heat row shows
# macOS's thermal pressure instead: the state it throttles on.
ncpu=$(sysctl -n hw.ncpu 2>/dev/null); [ "${ncpu:-0}" -gt 0 ] 2>/dev/null || ncpu=1
# ps reports each process's recent share of one core; summed over all cores.
cpu_pct=$(ps -A -o %cpu= | awk -v n="$ncpu" '{ s += $1 } END { v = int(s / n + 0.5); print (v > 100 ? 100 : v) }')
load=$(sysctl -n vm.loadavg 2>/dev/null | awk '{ print $2 }')
mem_gb=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1073741824 ))
# The kernel's memorystatus level is the share of memory it counts as free.
mem_free=$(sysctl -n kern.memorystatus_level 2>/dev/null); mem_pct=$(( 100 - ${mem_free:-100} ))
gpu_pct=$(ioreg -r -d 1 -c IOAccelerator 2>/dev/null | grep -o '"Device Utilization %"=[0-9]*' | head -1 | cut -d= -f2)
therm=$(notifyutil -g com.apple.system.thermalpressurelevel 2>/dev/null | awk '{ print $2 }')

HWL=(CPU Mem GPU Heat); HVP=(); HVC=(); HDP=(); HDC=()
val "$cpu_pct";        HVP[0]=$VP; HVC[0]=$VC; HDP[0]="load ${load}"; HDC[0]="${DET}load ${load}${R}"
val "$mem_pct";        HVP[1]=$VP; HVC[1]=$VC
HDP[1]="$(( mem_gb * mem_pct / 100 ))/${mem_gb}G"; HDC[1]="${DET}${HDP[1]}${R}"
val "${gpu_pct:-0}";   HVP[2]=$VP; HVC[2]=$VC; HDP[2]=""; HDC[2]=""
case "${therm:-0}" in
  0) HVP[3]="Nominal";  HVC[3]="${OK}Nominal${R}" ;;
  1) HVP[3]="Moderate"; HVC[3]="${WARN}Moderate${R}" ;;
  2) HVP[3]="Heavyꜝ";   HVC[3]="${CRIT}Heavy${R}${BAD}ꜝ${R}" ;;
  3) HVP[3]="Trappingꜝ"; HVC[3]="${CRIT}Trapping${R}${BAD}ꜝ${R}" ;;
  *) HVP[3]="Sleepingꜝ"; HVC[3]="${CRIT}Sleeping${R}${BAD}ꜝ${R}" ;;
esac
HDP[3]=""; HDC[3]=""
HW=0; for i in 0 1 2 3; do [ ${#HVP[$i]} -gt "$HW" ] && HW=${#HVP[$i]}; done

L=0
for i in 0 1 2 3; do [ ${#LP[$i]} -gt "$L" ] && L=${#LP[$i]}; done
# Each right row's printed width, so the hardware column's divider lines up.
RW=(); RMAX=0
for i in 0 1 2 3; do
  RW[$i]=$(( 8 + ${#BRP[$i]} ))
  [ -n "${GRP[$i]}" ] && RW[$i]=$(( 8 + MW + 2 + ${#GRP[$i]} ))
  [ "${RW[$i]}" -gt "$RMAX" ] && RMAX=${RW[$i]}
done

for i in 0 1 2 3; do
  [ "$i" -gt 0 ] && printf '\n'
  printf '%s%s' "${LC[$i]}" "$(spaces $(( L - ${#LP[$i]} )))"
  printf '%s' "${DIV} │ ${R}${LAB}$(printf '%-8s' "${RLAB[$i]}")${R}${BRC[$i]}"
  if [ -n "${GRP[$i]}" ]; then
    printf '%s%s' "$(spaces $(( MW - ${#BRP[$i]} + 2 )))" "${GRC[$i]}"
  fi
  printf '%s' "$(spaces $(( RMAX - RW[$i] )))${DIV} │ ${R}${LAB}$(printf '%-5s' "${HWL[$i]}")${R}${HVC[$i]}"
  if [ -n "${HDP[$i]}" ]; then printf '%s%s' "$(spaces $(( HW - ${#HVP[$i]} + 2 )))" "${HDC[$i]}"; fi
done
