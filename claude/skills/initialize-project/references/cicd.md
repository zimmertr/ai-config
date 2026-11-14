# CI/CD

The pipeline is zimmertr/yggdrasil's reusable workflows. A new repo calls
them; it never copies a workflow or writes its own version of one. Each
module's inputs, permissions and check names are in yggdrasil's
[`docs/CONFIGURATION.md`](https://github.com/zimmertr/yggdrasil/blob/main/docs/CONFIGURATION.md),
and its "An example caller" names the repo to copy the callers from.

## Calling the modules

1. **Pin every module to a release's commit SHA**, with the version in a
   comment (`@<sha> # v1.0.1`), so Renovate moves it.
2. **Grant each caller only what its module asks for**, with
   `permissions: {}` at the top of the workflow. The release caller grants
   `contents: write` and `packages: write`, even with no image: GitHub
   refuses to start a run whose caller grants less than a called job asks
   for, and the PR still looks green, because the release isn't a required
   check.
3. **`concurrency` on the release caller only**: `group: release`,
   `cancel-in-progress: false`. `pr-title` sets its own group: don't give
   its caller one.
4. **Checks are named `caller / callee`**, such as `Lint / zizmor` or
   `PR Title / PR Title`. The repo's file in yggdrasil requires them by those
   names (see [repo.md](repo.md)), so renaming a caller job strands PRs on a
   check that never reports.

## Versioning

5. **Conventional commits and SemVer from the first commit.** The repo
   merges by squash only, with the PR title as the commit title and the PR
   body as its message. The release module's GitVersion reads the bump from
   that title alone:
   - major: any type below with `!` before the colon (`feat!:`, `fix(api)!:`)
   - minor: `feat:` or `feat(scope):`
   - patch: `fix`, `perf`, `refactor`, `chore`, `docs`, `style`, `test`, `ci`,
     `build`, each with an optional `(scope)`

   The body never counts, so a `BREAKING CHANGE:` footer is not a major. The
   first release is v0.1.0. A repo needs no `GitVersion.yml`: the module's
   default applies unless the repo keeps its own.
6. **The `pr-title` module** fails a title no pattern reads. Its check is
   required.

## The release, on every merge to main

7. **The `release` module** runs on every push to main. In order: the
   version; each image built for its platforms, with SBOM and provenance
   attestations, pushed to `ghcr.io/<owner>/<image>` under the version only
   (no `latest`) with the job's own `GITHUB_TOKEN`; a Trivy scan of each
   image on each platform; the git tag and an immutable GitHub release with
   notes from the PR titles, only once every scan passes; then one
   self-merging PR in each deploy repo, pinning the image by digest.
8. **The module releases only from main's newest commit.** When merges land
   close together, GitHub keeps one run waiting and cancels the rest, so some
   versions are skipped. Nothing is lost: the next release counts every
   merge.
9. **Fix forward.** A bad release is fixed by the next one. The pipeline is
   the only way to deploy: never hand-build, hand-push or hand-edit a
   deployed tag. A release that failed part way is finished with "Re-run
   failed jobs", or by releasing again from main.
10. **Conditional (Helm chart):** the `release` module pushes the chart
    too. Name it in `charts`, with the image and where its digest goes in
    the values: the module pushes it to `oci://ghcr.io/<owner>` after the
    tag, and opens the deploy bump (the chart's version, in `deploys`) only
    after that. On PRs the `chart` module lints it and renders it with its
    defaults, then runs the helm-unittest suites in the chart's `tests/`
    folder (yggdrasil record 0060). Never Bash renders in its deprecated
    `test` input. Its check, `Chart / Chart`, is required.

## Workflow hygiene

11. Pin every action to a full commit SHA, with its version in a comment,
    and every base image as `tag@digest`. Renovate moves both, and the
    repo's "require actions to be pinned" setting refuses anything else.
12. Least privilege, as in step 2, and the only checkout that keeps its token
    is the one that pushes. Pass titles and other user input through `env:`,
    never into the shell line.
13. A `timeout-minutes` on every job of the repo's own, because releases
    queue behind each other.
14. Pass secrets only to the step that needs them. Never hand a token to a
    third-party action in a step that can rewrite `$GITHUB_PATH` or
    `$GITHUB_ENV` for a later step that holds a secret.

## Pull request checks

15. Every PR runs:
    - the `lint` module: actionlint, zizmor's pedantic audits and Semgrep's
      base-image digest rule. It replaces any workflow or Dockerfile check
      the repo would otherwise write itself.
    - the `pr-title` module
    - the tests, with the coverage report
    - a linter (for example ruff, ESLint) that also fails a broad `except`
      that swallows its error: it re-raises, logs its traceback, or carries
      a suppression with the reason beside it
    - a type checker for every typed language (`tsc --noEmit`, mypy)
    - when the project ships an image: the `docker-build` module, which runs
      hadolint, builds the image, scans it with Trivy, keeps a sticky scan
      comment on the PR, and runs the repo's container-structure-test file
      against it (its `structure-test` input, yggdrasil record 0060), never a
      Bash smoke test. A check the tool can't hold, such as one against a
      running server, goes to TJ first
    - **conditional (web UI):** Lighthouse CI budgets and a browser smoke
      test with axe
16. **Conditional (previews):** a preview environment per PR, and a cache
    cleanup workflow when caches pile up.
    1. yggdrasil's `pr-preview` module builds each PR's image on
       `pull_request` as `<image>-pr:pr-<N>-<head sha>`, and labels the
       maintainer's own PRs `create pr container` (yggdrasil record 0059).
    2. An ApplicationSet with Argo CD's pull request generator, in
       Kubernetes-Manifests beside the app's folder, runs each labelled PR's
       chart at `pr-<N>.<host>`. The release bumps its chart version with the
       live app's.
    3. A preview never gets production's credentials. It runs on made-up
       data, and a banner names the PR and the commit.
    4. A preview lives for as long as its PR carries the label, and ends when
       the label comes off or the PR closes; there's no age limit. Previews
       share one namespace, apart from production's, with Pod Security
       `restricted`.

    hevy-garmin-sync and Bluebird are the worked examples.
17. Every CI check of the repo's own is also a `make` target that runs in
    Docker.
18. **Unused code is found on demand.** A `make check-unused` target (Knip,
    Vulture) runs before a refactor lands, and every allowlisted exception
    sits beside its reason.

## Delivery

19. **Conditional (Kubernetes):** GitOps through Argo CD and the
    Kubernetes-Manifests repo. Argo CD auto-syncs and reverts changes made
    outside git. The version and the image digest are pinned in git, and the
    release is the only thing that bumps them.
20. **Conditional (long-running, user-facing service on Kubernetes):**
    1. A Helm chart instead of hand-written manifests, inflated through
       Kustomize's `helmCharts` generator.
    2. Argo CD finds it through an ApplicationSet with a Git generator.
    3. The ApplicationSets and AppProjects are managed by the app-of-apps
       pattern from the root Application.
    4. The chart is published to GHCR as an OCI artifact, with a README for
       its values.
    5. The service deploys through Argo Rollouts with a canary or blue-green
       strategy, and a gate that checks the new version before it takes the
       traffic. The gate exercises only the service and what it deploys with,
       never a third party, so an outside outage can't fail or block a good
       release.
21. **Conditional (a cloud: AWS, Cloudflare and so on):** Terraform for
    every resource. No ClickOps, and no one-off API calls.
