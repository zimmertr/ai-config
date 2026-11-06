# Security

## Branch protection on main

1. A pull request is required for every change, admins included, with 0
   approving reviews. Stale reviews are dismissed.
2. Required checks: the test job and `PR Title`, plus every other PR check
   that must never be skipped. The branch need not be up to date
   (`strict: false`).
3. Every conversation must be resolved before merging.
4. No force-push and no deletion of main.
5. A ruleset asks Copilot to review every PR, drafts included. On 2026-11-05
   it had produced no reviews on Bluebird or hevy-trainer-sync; check whether
   Copilot code review is available on the account.

## Dependabot

6. Dependabot alerts and security updates are on.
7. Weekly version updates for every ecosystem the repo uses (the language's
   package files, `github-actions`, `docker`). Each PR title is
   `build(deps):`, which releases a patch (`commit-message: prefix: build,
   include: scope`). Language packages wait seven days after a release
   (`cooldown: default-days: 7`). Security updates skip the wait.
8. **Patch and minor updates merge themselves.** A `dependabot-auto-merge.yml`
   workflow arms squash auto-merge when Dependabot's metadata says
   `version-update:semver-patch` or `version-update:semver-minor`, and
   comments on the PR to say so. GitHub merges once the required checks pass
   and the conversations are resolved. Major updates, and digest-only base
   image updates, wait for the maintainer.
9. The merge uses an `AUTO_MERGE_PAT` **Dependabot** secret: a run Dependabot
   starts can't read Actions secrets, and a merge made with `GITHUB_TOKEN`
   would not start the release workflow.

## Scanning

10. **The release scans its own image** by digest with Trivy
    (`ignore-unfixed`, a shared `trivy.yaml`). A fixable Critical or High
    stops the GitHub release and the deploy; production stays on the
    previous release. The image runs `apt-get upgrade` (or `apk upgrade`)
    at build time, because base images lag their distribution's security
    fixes. When builds share a cache, BuildKit reuses that layer and a fixed
    CVE never arrives, so the upgrade goes after a build argument that
    changes on every build (the commit, the build time): BuildKit keys a
    `RUN` on every argument in scope. Only `USER`, `EXPOSE`, `HEALTHCHECK`
    and `CMD` follow it, so the rerun repeats no build work. Bluebird:
    record 0197.
11. **Choose the base image by measured findings.** Scan the candidates with
    Trivy, pick the one with the fewest findings that have no fix, and record
    why. A multi-platform image is scanned per platform, by digest. Bluebird:
    records 0001 (Alpine over Debian slim) and 0105.
12. **A weekly scan** of the latest release's image uploads SARIF to the
    Security tab and fails only on a fixable Critical or High.
13. **CodeQL default setup** for every language in the repo, `actions`
    included.
14. **Secret scanning with push protection** is on.

## Dependencies

15. **Direct pins in one file, installs from a hashed lock.** A person edits
    one file of direct pins (`requirements.in`, `package.json`). The install
    reads a lock generated from it: `pip-compile --generate-hashes` then
    `pip install --require-hashes`, or `npm ci` from `package-lock.json`. A
    `make` target regenerates the lock, and a pin change ships with its
    regenerated lock in the same PR. Bluebird: record 0099.
16. **No install scripts.** Every `npm ci` passes `--ignore-scripts`, and a
    test fails one that doesn't.
17. **Pin what you import.** A convenience extra that pulls in packages the
    code never uses is replaced by direct pins of the packages it does use.
    Bluebird: record 0200.

## Releases and images

18. GitHub releases are immutable, and so are image tags on the registry
    (Docker Hub's immutable tags, with the rule `.*`).

## Secrets

19. Secrets live in GitHub Actions secrets, Dependabot secrets, or the
    cluster's Secrets, and nowhere else. Never in the repo, fixtures, logs,
    image layers or build arguments. The maintainer's tokens are in
    `~/.claude/secrets.json`.
20. Each repo's `docs/CICD.md` lists every secret, where it lives, and which
    job uses it.

## Reporting

21. Private vulnerability reporting is on, and `SECURITY.md` says what's
    supported, how to report privately, what to expect, and what's in scope.
