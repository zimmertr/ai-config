# The repository

## Files

1. `LICENSE`, from the interview's choice. Ask before creating the repo.
   The repo itself starts from `zimmertr/yggdrasil-repo-template`, which holds
   the `pr-title` and `lint` callers and `.github/renovate.json` (see Settings).
2. `.gitignore` for the language and tooling, and `.dockerignore` beside the
   `Dockerfile`.
3. `README.md`. The maintainer owns it: it is written in the maintainer's
   voice, kept true in every PR, and never restructured, rewritten or given
   badges, banners or AI-flavoured prose. Detail lives in `docs/`, and the
   README points to it. It starts from these sections, with the words left
   to the maintainer: Summary, How It Works, Quick Start, the docs table,
   Support and License. Anything longer than a paragraph goes in `docs/`.
   The project's icon (item 9) sits above the first section. It is the
   project's mark, not a banner, and the only image the README starts with.
4. No `SECURITY.md` of its own. The owner's `.github` repo serves one to
   every repo, from the single copy in zimmertr/yggdrasil's
   `community-health-files/` (its record 0041). See
   [security.md](security.md).
5. No `CONTRIBUTING.md` of its own. The owner's `.github` repo serves one
   too, from the same folder (yggdrasil's record 0055). A repo writes its
   own only when it has a process the shared one can't describe, and then
   the file is complete in itself: GitHub shows it in place of the shared
   one.
6. `NOTICES.md`, when third parties need credit: the data providers, and the
   software bundled in the shipped image, each with its license. A test
   holds it to the manifests (see [docs.md](docs.md), License notices).
7. No `.github/ISSUE_TEMPLATE/` of its own: the bug and proposal templates
   come from the owner's `.github` repo too. Any template in the repo hides
   all of the shared ones. The repo's area labels go in its `CLAUDE.md`
   Issues section.
8. `CLAUDE.md` (see [docs.md](docs.md)).
9. The project's icon: one hand-drawn SVG, `viewBox="0 0 32 32"`, a
   rounded tile (`rx="8"`) in the project's main colour with a white glyph.
   To choose it, draw ten options on a Design canvas Artifact, each at
   112 px, and at 32 px and 16 px on light and dark backgrounds, with any
   mark the UI lays over it (such as a status dot on the favicon) in
   place, and let the maintainer pick. Every option still reads at 16 px,
   and no two of its parts touch or overlap. That one file is the single
   source: the README shows it at the top
   (`<img src="..." alt="" width="96">`), a UI serves
   it as its favicon and header mark, and a Helm chart's `icon:` is its
   raw.githubusercontent.com URL. It lives where the app serves it, or in
   `docs/images/` when nothing does.
10. The social preview: `docs/social-preview.png`, 1280x640, with the HTML
    or SVG it is drawn from committed beside it, so anyone can draw it
    again. It shows the icon tile large on the left, the repo's name over
    its description, and the project's accent colours, on the project's
    dark background. The subtitle is the repo's GitHub description word
    for word, as set in its yggdrasil file (see Settings). Render it in
    Docker, never on the workstation, with headless Chrome and the fonts
    and the icon mounted read-only:
    `docker run --rm -u 0 -v <dir>:/work zenika/alpine-chrome --no-sandbox --hide-scrollbars --allow-file-access-from-files --window-size=1280,640 --screenshot=/work/social-preview.png file:///work/social-preview.html`.
    A PR that changes the icon or the description draws it again in the
    same PR. GitHub has no API, and the Terraform provider no setting, that
    uploads it, so the maintainer uploads it by hand under Settings, Social
    preview, once the repo exists and again after every change.

## Settings

The repo is created by one yggdrasil PR that adds `repos/<owner>/<name>.yml`
(yggdrasil's [`docs/USAGE.md`](https://github.com/zimmertr/yggdrasil/blob/main/docs/USAGE.md),
"A new repo"). The file holds only what differs from the defaults: the
description, and `required_checks`. The merge creates the repo from the
template, with every setting below, the rulesets and the security settings.
Change a setting there, never by hand. The social preview (item 10) is the
one exception, because nothing but the web UI can set it.

11. Squash merge only, with the PR title as the commit title and the PR body
    as the message. No merge commits, no rebase merges.
12. Auto-merge allowed, head branches deleted on merge, the "Update branch"
    button on, and the wiki off.
13. Branch protection, dependency updates and scanning as in
    [security.md](security.md).

## Branching

14. Trunk-based development: short-lived branches off main, each merged
    through one PR. One PR per feature or change, even a large one, and
    fewer, larger PRs over many small ones.
15. A PR's title is `type(scope): summary`, because it picks the release
    version (see [cicd.md](cicd.md)).

## Issues

16. GitHub Issues track every bug, feature and task. File each with the
    `create-issue` skill, which sets the format and the labels: one priority
    (`P1` to `P3`), one type, every area that applies, and the session's
    label.
17. The repo's CLAUDE.md has an "Issues" section that `create-issue` reads:
    who the plain-language reader is, the repo's CI gates, the constraints an
    implementer must know, and the area labels.
