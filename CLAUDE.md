# ai-config

TJ's Claude Code configuration. `claude/` mirrors `~/.claude`: `~/.claude/CLAUDE.md`, `~/.claude/settings.json`, `~/.claude/statusline.py` and each folder in `~/.claude/skills/` that came from here are symlinks into TJ's checkout at `~/git/personal/ai-config`, so whatever is on that checkout's main is live.

## Rules

- Change anything here only through a PR that TJ approves. A merge changes how every session behaves once the live copy pulls it.
- Work in a scratchpad clone, never in `~/git/personal/ai-config`, which is the live copy. The one exception: right after merging a PR here, fast-forward it with `git -C ~/git/personal/ai-config pull --ff-only` so the change is live at once. Never leave that step to TJ.
- Never commit a secret. `settings.json` holds settings, not tokens; tokens stay in `~/.claude/secrets.json`, which is not in this repo.
- A skill is a folder under `claude/skills/` with a `SKILL.md` (frontmatter `name` and `description`, under 500 lines) and any files it links to. A new skill needs its symlink, which the README's setup loop makes.
- CI is zimmertr/yggdrasil's `pr-title` and `lint` modules, pinned by commit SHA with the version beside it. Renovate bumps the pin, and a patch or minor merges itself. The PR title is `type(scope): summary`. `test.yml` is this repo's own: pytest over `tests/` on Python 3.9, the version macOS ships, so `claude/statusline.py` keeps to the standard library and 3.9 syntax.
- This repo took a trimmed set of the files a new project starts with (zimmertr/yggdrasil record 0038). When a change here makes a decision, write its record; when it needs `CONTRIBUTING.md` or a `docs/` page, add it in the same PR.

## Issues

`create-issue` reads this section.

- **The reader**: TJ, looking at the board to decide what to do next.
- **The gates**: the change is in a PR; any skill touched keeps valid frontmatter and stays under 500 lines; the README's setup steps still work.
- **The constraints**: nothing here may hold a secret; a change to `claude/CLAUDE.md` or `claude/settings.json` changes every session, so it says so in the PR; work happens in a scratchpad clone.
- **The areas**: `skills` (anything under `claude/skills/`), `global-rules` (`claude/CLAUDE.md`), `settings` (`claude/settings.json`), `ci` (reusable workflows and actions), `terraform` (repo settings as code), `helm` (shared charts), `plugins` (the plugin marketplace).
