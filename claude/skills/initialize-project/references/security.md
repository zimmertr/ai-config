# Security

## Branch protection on main

yggdrasil's repo module sets everything in this section and the next from the
repo's file there (see [repo.md](repo.md)). Never set one by hand: the next
apply puts it back.

1. A pull request is required for every change, admins included, with 0
   approving reviews. Stale reviews are dismissed.
2. Required checks: the test job, `PR Title / PR Title` and the three
   `Lint / ...` checks, plus every other PR check that must never be skipped,
   listed in the repo file's `required_checks`. The branch need not be up to
   date (`strict: false`).
3. Every conversation must be resolved before merging.
4. No force-push and no deletion of main.
5. No Copilot review ruleset: on both reference projects it produced no
   reviews.

## Dependency updates

6. Dependabot alerts and security updates are on.
7. Renovate proposes version updates. The template's `.github/renovate.json`
   extends yggdrasil's shared preset,
   `github>zimmertr/yggdrasil//defaults/renovate` (its record 0056), and the
   maintainer's Renovate installation covers every repo of the account, so a
   new repo needs no setup. Every release waits seven days before it is
   proposed, except yggdrasil's own modules and an image whose registry
   gives no publish date. Each PR title is `chore(deps):` or `fix(deps):`,
   which releases a patch. Security updates skip the wait.
8. **Everything below a major merges itself.** Renovate arms squash
   auto-merge on its own PRs, and GitHub merges once the required checks
   pass and the conversations are resolved. A major waits for the
   maintainer.
9. A repo adds a rule to its own `renovate.json` only where it differs from
   the preset. A private repo has no required checks, so it turns
   auto-merge off.

## Scanning

10. **The release scans its own image** with Trivy, each platform
    (`ignore-unfixed`, yggdrasil's default `trivy.yaml` unless the repo keeps
    its own). A fixable Critical or High
    stops the GitHub release and the deploy; production stays on the previous
    release. The image runs `apt-get upgrade` (or `apk upgrade`) at build
    time, because base images lag their distribution's security fixes. Put the
    upgrade after a build argument that changes on every build (the commit,
    the build time), whether or not the build uses a cache today. A builder
    with no cache reruns the layer anyway. Once a cache is added (`cache-from:
    type=gha`), BuildKit reuses the layer, because
    it keys a `RUN` on every argument in scope, and a fixed CVE never arrives.
    Only `USER`, `EXPOSE`, `HEALTHCHECK` and `CMD` follow it.
11. **Choose the base image by measured findings.** Scan the candidates with
    Trivy, pick the one with the fewest findings that have no fix, and record
    why. A multi-platform image is scanned per platform, by digest.
12. **A weekly scan** of the latest release's image, through yggdrasil's
    `image-scan` module, uploads SARIF to the Security tab and fails only on a
    fixable Critical or High.
13. **CodeQL default setup** for every language in the repo, `actions`
    included.
14. **Secret scanning with push protection** is on.

## Dependencies

15. **Direct pins in one file, installs from a hashed lock.** A person edits
    one file of direct pins (`requirements.in`, `package.json`). The install
    reads a lock generated from it: `pip-compile --generate-hashes` then `pip
    install --require-hashes`, or `npm ci` from `package-lock.json`. A `make`
    target regenerates the lock, and a pin change ships with its regenerated
    lock in the same PR. A test holds the lock to the pins: every direct pin
    locked at its version, every locked package hashed, and the image
    installing the lock with hashes required.
16. **No install scripts.** Every `npm ci` passes `--ignore-scripts`, and a
    test fails one that doesn't.
17. **Pin what you import.** A convenience extra that pulls in packages the
    code never uses is replaced by direct pins of the packages it does use.

## Releases and images

18. GitHub releases are immutable. Images and charts go to GHCR, pushed
    with the job's own `GITHUB_TOKEN`: never to Docker Hub, and never with a
    stored registry secret. GHCR has no immutable tags, so every deploy pins
    the image's digest beside its tag (yggdrasil's record 0052).

## Secrets

19. Secrets live in GitHub Actions secrets, Dependabot secrets, or the
    cluster's Secrets, and nowhere else. Never in the repo, fixtures, logs,
    image layers or build arguments. The maintainer's tokens are in
    `~/.claude/secrets.json`.
20. Each repo's `docs/CICD.md` lists every secret, where it lives, and which
    job uses it.

## Reporting

21. Private vulnerability reporting is on. The owner's shared `SECURITY.md`
    (see [repo.md](repo.md)) says what's supported, how to report
    privately, what to expect, and what's in scope.
