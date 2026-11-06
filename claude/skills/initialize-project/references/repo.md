# The repository

## Files

1. `LICENSE`, from the interview's choice. Ask before creating the repo.
2. `.gitignore` for the language and tooling, and `.dockerignore` beside the
   `Dockerfile`.
3. `README.md`. The maintainer owns it: it is written in the maintainer's
   voice, kept true in every PR, and never restructured, rewritten or given
   badges, banners or AI-flavoured prose. Detail lives in `docs/`, and the
   README points to it. It starts from Bluebird's sections, with the words
   left to the maintainer: Summary, How It Works, Quick Start, the docs
   table, Support and License. Anything longer than a paragraph goes in
   `docs/`. Bluebird: record 0005.
4. `SECURITY.md` (see [security.md](security.md)).
5. `CONTRIBUTING.md`: how to send a change. The `make` targets, tests with
   every behaviour change, and the docs page that owns the topic.
6. `NOTICES.md`, when third parties need credit: the data providers, and the
   software bundled in the shipped image, each with its license. A test
   holds it to the manifests (see [docs.md](docs.md), License notices).
7. `.github/ISSUE_TEMPLATE/`: a bug and a proposal template, with blank
   issues off.
8. `CLAUDE.md` (see [docs.md](docs.md)).

## Settings

9. Squash merge only, with the PR title as the commit title and the PR body
   as the message. No merge commits, no rebase merges.
10. Auto-merge allowed, head branches deleted on merge, the "Update branch"
    button on, and the wiki off.
11. Branch protection, Dependabot and scanning as in
    [security.md](security.md).

## Branching

12. Trunk-based development: short-lived branches off main, each merged
    through one PR. One PR per feature or change, even a large one.
13. A PR's title is `type(scope): summary`, because it picks the release
    version (see [cicd.md](cicd.md)).

## Issues

14. GitHub Issues track every bug, feature and task. File each with the
    `create-issue` skill, which sets the format and the labels: one priority
    (`P1` to `P3`), one type, every area that applies, and the session's
    label.
15. The repo's CLAUDE.md has an "Issues" section that `create-issue` reads:
    who the plain-language reader is, the repo's CI gates, the constraints an
    implementer must know, and the area labels.
