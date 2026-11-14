# ai-config

My Claude Code setup: the global `CLAUDE.md` every session loads, my `settings.json`, my status line, and the skills I use across projects.

## What's here

- `claude/CLAUDE.md`: the rules that apply in every repo.
- `claude/settings.json`: my Claude Code settings.
- `claude/statusline.py`: my status line. A row for the machine (each CPU core, memory, GPU, network and temperature), then a bar each for context and my usage limits, Fable's weekly one included. Beside them sit the model and effort with how much of the prompt cache's life has gone, the git branch and directory, the Kubernetes context, and the session's cost, turns, short ID and name. Every session shares the newest usage limits any of them has seen. It only needs the `python3` from Apple's Command Line Tools. However, the temperature only shows once you install [iSMC](https://github.com/dkorunic/iSMC) with `brew install dkorunic/tap/ismc`, since macOS has no way to read it without sudo.
- `claude/skills/`: my own skills. `initialize-project` starts a new project to my standards, and `create-issue` files GitHub issues the way I like them.

## Setup

`~/.claude` points into this checkout, so a merge here is live once it's pulled. Claude pulls right after it merges one:

```sh
git clone https://github.com/zimmertr/ai-config.git ~/git/personal/ai-config
ln -s ~/git/personal/ai-config/claude/CLAUDE.md ~/.claude/CLAUDE.md
ln -s ~/git/personal/ai-config/claude/settings.json ~/.claude/settings.json
ln -s ~/git/personal/ai-config/claude/statusline.py ~/.claude/statusline.py
for s in ~/git/personal/ai-config/claude/skills/*/; do ln -s "${s%/}" ~/.claude/skills/; done
```

Move any existing file out of the way before linking it.
