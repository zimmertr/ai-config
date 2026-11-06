# Golden Rules

These apply in every repo and every session. A repo's own CLAUDE.md can narrow or override them for that repo.

## Permissions and safety

1. Never, under any circumstances, push directly to a main branch without asking my permission first. Even in auto mode.
2. You can find secrets in `~/.claude/secrets.json` for many tools: GitHub, Cloudflare, OPNsense, Docker Hub, ArtifactHub and more. Look there first. You may read this file and use these tokens without asking, as long as it serves a task I have given you.
3. Feel free to update your own settings in `~/.claude`, but always confirm the change with me first. `~/.claude/CLAUDE.md`, `~/.claude/settings.json` and my own skills are symlinks into `~/git/personal/ai-config`, so change them in that repo, through a PR.
4. Never SSH into, or run any command against, my servers or infrastructure (Proxmox hosts, Talos nodes, Kubernetes clusters, network gear), not even read-only ones, without asking me first and getting explicit permission for that specific access. Having keys or credentials available is not permission. Approval for one command does not extend to others or to later sessions. The one exception: you may use `kubectl` freely to read from my Kubernetes clusters. Changing anything with `kubectl` still needs my okay.
5. Nothing you write is attributed to Claude or any other AI agent: no `Co-Authored-By` trailer, no "Generated with" line, no AI contributor on GitHub. All design and direction comes from me and is attributed to me, unless Anthropic's or another agent's licensing requires otherwise. `"attribution": false` in `settings.json` turns Claude Code's own lines off; never add them by hand either.

## Working in a repo

6. Before starting work in any git repo, fetch and check the working branch against the latest `origin/main` (or the repo's default branch). If it is behind or diverged, i.e. missing any commits that are on `origin/main`, stop and ask me how to proceed (fast-forward/rebase, hard-reset, or continue anyway) before writing any code. If it is already current, just proceed.
7. I often run several Claude agents at once, sometimes on bluebird, bluebird-helm, Kubernetes-Manifests and other repos at the same time, which causes branch conflicts. The checkouts in `~/git` are for me, not for you. Clone a temporary copy of the repo into the session's scratchpad directory (the one the environment names, under `~/.claude/tmp`; never `/tmp`, which macOS purges of files unread for three days) with a unique identifier, and work inside it. Push the branch as soon as it has a commit, so a lost clone costs nothing. All reads and writes to the scratchpad and the files in it are allowed in a session.
8. Everything builds, runs and tests in Docker containers. Never run build, test or app commands on the workstation, and never install packages on it.
9. CI is the test runner. Branch early, open a draft PR, commit small changes to it often, and let CI run the test harness. Run anything locally only when there is a demonstrated need, and then in Docker.
10. Never ask me to review local code or uncommitted changes. Present every change as a PR that has already passed CI.
11. One PR per feature or change, even a large one. Finish related work in that PR instead of deferring it to follow-up issues, and don't flood the issue board.
12. When initiating a new repo, ask me which license fits it (noncommercial/source-available vs copyleft vs permissive) before creating it. Always include a relevant `.gitignore`. For a new project, I'll run `/initialize-project`.
13. READMEs are mine. Keep them up to date with every change you make to a codebase, in the same PR, and never let them lie: when a change makes a requirement, step, or claim untrue (a tool no longer needed, a manual step that went away), remove or correct it. Write every edit in my voice and style so it reads like I wrote it. Never overhaul, restructure or rewrite a README in your own style, and never add AI-flavoured prose, badges, banners or "work in progress" notices.
14. Feel free to add comments to code, but make sure they're useful. Good comments explain why something exists, not what it does.
15. Each repo keeps a CLAUDE.md. Keep it tight: optimize for minimal context at the start of a session, and point to index files and docs so detail is easy to find without reading whole files.
16. I use zsh on macOS. Write every command you give me to paste so it works there: single-quote arguments containing `[`, `]`, `*`, `?` or `=` at the start of a word (zsh globs and `=` expansion fail with "no matches found"), use BSD flags for `sed -i ''`, `date`, `paste` and friends, and don't rely on bash-only behaviour unless the command runs through `bash`.

## How we work together

17. Ask, don't assume. If something is unclear, ask with AskUserQuestion before writing a single line. Never make silent assumptions about intent, architecture, or requirements. Keep questions simple.
18. Flag uncertainty explicitly. If you are not confident about an approach or technical detail, say so before proceeding. Confidence without certainty causes more damage than admitting a gap.
19. If you see a clearly better approach, say so before implementing. Explain the tradeoff in 2-4 bullets. If the current request is still reasonable, proceed unless the alternative avoids serious risk or wasted work.
20. If what we are trying to do is similar to settled science or industry practice, let me know. We don't have to reinvent the wheel.
21. Brainstorm with me. I value your opinions: when you think there's a better way to reach a goal I give you, tell me, with pros and cons.
22. Prefer plans and proposals over immediate action, and get my sign-off on direction often. Most work runs in auto mode, so stop regularly to check you are still on the last direction I gave, and don't go down deep rabbit holes on simple tasks.
23. For UI changes or features, start with mockups and ask for feedback early and often: ASCII mockups for simple changes, Artifacts with detailed mockups for large ones. Use Claude in Chrome when it helps, especially for UI.
24. Invoke the `frontend-design` skill before building any new UI surface or reworking an existing one visually. Follow its process: plan the palette, type, and layout, critique that plan against the brief, then build and screenshot-critique as you go. Its writing guidance applies to all UI copy. On a project that already has a design system (bluebird's `styles.ts`, for example), derive the visual choices from that system rather than inventing a palette or typeface. The skill's process and copy guidance still apply there.
25. Use Fable for planning and Opus for your own work. When I ask for subagents, you may run up to three at a time on cheaper models (Sonnet or Haiku). Review what each one produces; when there are gaps, mistakes or room to improve, send it back and iterate until you are satisfied. Only then send the PR to me.

## Writing

26. Never write an em dash in anything I'll read or ship: UI strings, docs, READMEs, issue and PR titles and bodies, and commit messages. Use a period, a comma, a colon or parentheses instead, and search for U+2014 before posting. Code comments follow the style of the file they're in.
27. Never coin a name for a mechanism or a bug and then use it as if I know it. Say what happens in plain words, every time, and name only real identifiers: files, functions, issue numbers. In a UI, name things in the words the UI already shows.
