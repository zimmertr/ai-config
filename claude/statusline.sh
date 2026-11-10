#!/usr/bin/env bash
# Claude Code status line. Reads session-context JSON on stdin and prints a
# four-row, column-aligned, color-coded status. Wired via ~/.claude/settings.json
# as `bash ~/.claude/statusline.sh`.
#
# Rows:
#   Claude: Model: <name> | Effort: <lvl> | Context: <tok>k · (AC: <pct>%) (Win: <pct>%) | Name: <short name> | ID: <session uuid>
#           (AC is how far the context has climbed toward the auto-compact
#           threshold; Win is how full the model's whole window is. With
#           auto-compact on, Win can never pass the AC point, so it is only
#           informative when compaction is disabled, e.g. DISABLE_AUTO_COMPACT=1.
#           Name is what ListAgents and SendMessage address a session by,
#           e.g. bluebird-2c; it is omitted when no registry entry matches.)
#   Usage:  Session: <pct>% (5h) | Resets: <t> | Cost: $<n> | 7d Limits: <pct>% (All) <pct>% (Fable)
#   File:   Dir: <fs path> | Branch: <branch> <↑ahead ↓behind> | Dirty: <n>
#           (Branch/Dirty only shown inside a git repo; arrows track the
#           branch's own upstream.)
#   K8s:    Context: <kube-context> | Namespace: <ns>
#
# Percentages colored by severity (green <50 / yellow <80). Session(5h), 7d and
# Win at >=80%, AC at >=75%, and the Context token count above 250K render as a
# bold-white-on-RED-background rectangle.

input=$(cat)

IFS=$'\t' read -r model effort ctx ctx_tok five_pct five_reset seven_pct seven_reset cost sid win mid <<EOF
$(echo "$input" | jq -r '[
  .model.display_name // "?",
  (.effort.level // "?"),
  (.context_window.used_percentage // 0),
  (.context_window.total_input_tokens // 0),
  (.rate_limits.five_hour.used_percentage // 0 | round),
  (.rate_limits.five_hour.resets_at // 0),
  (.rate_limits.seven_day.used_percentage // 0 | round),
  (.rate_limits.seven_day.resets_at // 0),
  (.cost.total_cost_usd // 0),
  (.session_id // "?"),
  (.context_window.context_window_size // 0),
  (.model.id // "")
] | @tsv')
EOF

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
dir="${cwd/#$HOME/~}"

# The short session name (`bluebird-2c`) is the address other sessions message
# this one by, and the stdin payload does not carry it: Claude Code's messaging
# registry keeps it per process in ~/.claude/sessions/<pid>.json, keyed by the
# same session id, so it is read from there. A session with no entry (started
# without messaging) shows no Name cell.
sname=$(jq -r --arg sid "$sid" 'select(.sessionId == $sid) | .name // empty' \
  "$HOME"/.claude/sessions/*.json 2>/dev/null | head -1)
effort=$(printf '%s' "$effort" | awk '{print toupper(substr($0,1,1)) substr($0,2)}')

in_git=0; branch="—"; dirty=0; ahead=0; behind=0
if git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  in_git=1
  branch=$(git -C "$cwd" branch --show-current 2>/dev/null); [ -z "$branch" ] && branch="—"
  dirty=$(git -C "$cwd" status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  if ab=$(git -C "$cwd" rev-list --left-right --count '@{upstream}...HEAD' 2>/dev/null); then
    behind=$(printf '%s' "$ab" | awk '{print $1}')
    ahead=$(printf  '%s' "$ab" | awk '{print $2}')
  fi
fi

# K8s context + namespace (namespace needs a second query; only when a context is set)
kube="—"; ns="—"
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
  [ "$1" -le 0 ] 2>/dev/null && { printf -- '—'; return; }
  d=$(( $1 - now ))
  [ "$d" -le 0 ] && { printf 'now'; return; }
  if   [ "$d" -ge 172800 ]; then printf '%dd%dh' "$(( d / 86400 ))" "$(( (d % 86400) / 3600 ))"
  elif [ "$d" -ge 3600 ];   then printf '%dh%dm' "$(( d / 3600 ))"  "$(( (d % 3600) / 60 ))"
  else                           printf '%dm'    "$(( d / 60 ))"
  fi
}
five_r=$(fmt_reset "$five_reset")

# Fable model-scoped weekly limit — not in the stdin payload, so it's pulled from
# the OAuth usage endpoint (same source as /usage) and cached; a background
# refresh at most every 5 min keeps the render itself fast and offline-safe.
fable_cache="$HOME/.claude/cache/fable-limit.json"
fable_stamp="$HOME/.claude/cache/fable-limit.stamp"
fable_pct=$(jq -r '.percent // empty' "$fable_cache" 2>/dev/null)
# Cache mtime tracks data freshness (only rewritten on a successful fetch); if
# the data is >3h old (expired token, extended offline) hide it rather than
# show a number that may be days out of date.
fable_age=999999
[ -f "$fable_cache" ] && fable_age=$(( now - $(stat -f %m "$fable_cache" 2>/dev/null || echo 0) ))
[ "$fable_age" -ge 10800 ] && fable_pct=""
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

# --- Palette (bright, high-contrast) ---
L='\033[1;96m'; K='\033[94m'; V='\033[97m'; G='\033[38;5;248m'; S="$G"; R='\033[0m'
pc() {          # VALUE WARN CRIT -> SGR color code
  if   [ "$1" -lt "$2" ]; then printf 92
  elif [ "$1" -lt "$3" ]; then printf 93
  else                         printf 91
  fi
}
pct_token() {   # VALUE [WARN=50] [CRIT=80]: sets PCT_COL + PCT_PLN; >=CRIT -> red rectangle
  local w="${2:-50}" c="${3:-80}"
  if [ "$1" -ge "$c" ]; then PCT_COL="\033[1;97;41m ${1}% \033[0m"; PCT_PLN=" ${1}% "
  else PCT_COL="\033[$(pc "$1" "$w" "$c")m${1}%\033[0m"; PCT_PLN="${1}%"; fi
}

if [ "${dirty:-0}" -gt 0 ]; then dirty_col="\033[93m${dirty}\033[0m"; else dirty_col="\033[92m0\033[0m"; fi
bsfx=""
[ "${ahead:-0}"  -gt 0 ] && bsfx="${bsfx} \033[92m↑${ahead}\033[0m"
[ "${behind:-0}" -gt 0 ] && bsfx="${bsfx} \033[91m↓${behind}\033[0m"

# CX sizes the Context cell on its own: it is far wider than the Cost cell under
# it, and padding Cost out to match left a hole in the Usage row.
LBL=8; C1=17; C2=14; C3=14; CX=36
lbl()  { printf '%b' "${L}$1${R}"; local p=$(( LBL - ${#1} )); [ "$p" -gt 0 ] && printf '%*s' "$p" ''; }
cell() { printf '%b' "$3"; local p=$(( $1 - ${#2} )); [ "$p" -gt 0 ] && printf '%*s' "$p" ''; }
sep()  { printf '%b' " ${S}|${R} "; }

# --- Row 1: Claude ---
lbl "Claude:"
cell "$C1" "Model: ${model}"     "${K}Model:${R} ${V}${model}${R}"; sep
cell "$C2" "Effort: ${effort}"   "${K}Effort:${R} ${V}${effort}${R}"; sep
pct_token "$ac_pct" 50 75; ac_col="$PCT_COL"; ac_pln="$PCT_PLN"
pct_token "$ctx"
# The plain string measures width with an ASCII dot: the middle dot is multibyte
# and ${#} counts bytes under the C locale the status line may run in.
# Past 250K tokens the raw count gets the red rectangle too, whatever the
# percentages say: on a 1M window that is still only ~25% Win.
if [ "${ctx_tok:-0}" -gt 250000 ] 2>/dev/null; then
  tok_col="\033[1;97;41m ${ctxk}k \033[0m"; tok_pln=" ${ctxk}k "
else tok_col="${V}${ctxk}k${R}"; tok_pln="${ctxk}k"; fi
cell "$CX" "Context: ${tok_pln} . (AC: ${ac_pln}) (Win: ${PCT_PLN})" \
  "${K}Context:${R} ${tok_col} ${S}·${R} ${G}(AC:${R} ${ac_col}${G})${R} ${G}(Win:${R} ${PCT_COL}${G})${R}"; sep
[ -n "$sname" ] && { printf '%b' "${K}Name:${R} ${V}${sname}${R}"; sep; }
printf '%b' "${K}ID:${R} ${V}${sid}${R}"

# --- Row 2: Usage (limits + session cost + context) ---
printf '\n'; lbl "Usage:"
pct_token "$five_pct"
cell "$C1" "Session: ${PCT_PLN} (5h)" "${K}Session:${R} ${PCT_COL} ${G}(5h)${R}"; sep
cell "$C2" "Resets: ${five_r}"        "${K}Resets:${R} ${V}${five_r}${R}"; sep
cell "$C3" "Cost: \$${sc}"            "${K}Cost:${R} ${V}\$${sc}${R}"; sep
pct_token "$seven_pct"
printf '%b' "${K}7d Limits:${R} ${PCT_COL} ${G}(All)${R}"
case "$fable_pct" in
  ''|*[!0-9]*) ;;  # no cached value yet (or stale/garbage) — omit the Fable part
  *) pct_token "$fable_pct"; printf '%b' " ${S}·${R} ${PCT_COL} ${G}(Fable)${R}" ;;
esac

# --- Row 3: File (git cells only render inside a work tree) ---
printf '\n'; lbl "File:"
if [ "$in_git" = 1 ]; then
  cell "$C1" "Dir: ${dir}" "${K}Dir:${R} ${V}${dir}${R}"; sep
  printf '%b' "${K}Branch:${R} ${V}${branch}${R}${bsfx}"; sep
  printf '%b' "${K}Dirty:${R} ${dirty_col}"
else
  printf '%b' "${K}Dir:${R} ${V}${dir}${R}"
fi

# --- Row 4: K8s ---
printf '\n'; lbl "K8s:"
cell "$C1" "Context: ${kube}" "${K}Context:${R} ${V}${kube}${R}"; sep
printf '%b' "${K}Namespace:${R} ${V}${ns}${R}"
