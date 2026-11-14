# ai-config

My Claude Code setup: the global `CLAUDE.md` every session loads, my `settings.json`, my status line, and the skills I use across projects.

## What's here

- `claude/CLAUDE.md`: the rules that apply in every repo.
- `claude/settings.json`: my Claude Code settings.
- `claude/statusline.py`: my status line. I wanted to see at a glance how close I am to my limits, so it's five rows in three columns. First come the charts: each CPU core, then a bar each for context and my 5 hour, weekly and Fable limits. Next to them sit the numbers that go with them: how close auto-compact is, the session's cost and turns, when each limit resets and its pace (where it lands at the reset if I keep going like this). Last come the names: the model and effort, the session's short ID and name, the directory, the git branch and the Kubernetes context. Anything past its limit turns coral and gets a box around it, and every session shares the newest usage limits any of them has seen. It only needs the `python3` from Apple's Command Line Tools.
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
