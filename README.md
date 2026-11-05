# ai-config

My Claude Code setup: the global `CLAUDE.md` every session loads, my `settings.json`, and the skills I use across projects.

## What's here

- `claude/CLAUDE.md`: the rules that apply in every repo.
- `claude/settings.json`: my Claude Code settings.
- `claude/skills/`: my own skills. `initialize-project` starts a new project to my standards, and `create-issue` files GitHub issues the way I like them.

## Setup

`~/.claude` points into this checkout, so a merge here is live once I pull:

```sh
git clone https://github.com/zimmertr/ai-config.git ~/git/personal/ai-config
ln -s ~/git/personal/ai-config/claude/CLAUDE.md ~/.claude/CLAUDE.md
ln -s ~/git/personal/ai-config/claude/settings.json ~/.claude/settings.json
for s in ~/git/personal/ai-config/claude/skills/*/; do ln -s "${s%/}" ~/.claude/skills/; done
```

Move any existing file out of the way before linking it.
