# CI/CD

The pipeline already runs in the projects named in [SKILL.md](../SKILL.md).
Copy it from them rather than writing it fresh, and read their
`docs/CICD.md` for why each piece is there.

## Versioning

1. **Conventional commits, SemVer and GitVersion from the first commit.** The
   repo merges by squash only, with the PR title as the commit title and the
   PR body as its message. GitVersion reads the bump from that title alone:
   - major: any type below with `!` before the colon (`feat!:`, `fix(api)!:`)
   - minor: `feat:` or `feat(scope):`
   - patch: `fix`, `perf`, `refactor`, `chore`, `docs`, `style`, `test`, `ci`,
     `build`, each with an optional `(scope)`

   The body never counts, so a `BREAKING CHANGE:` footer is not a major.
2. **Seed the first version.** Use `next-version` with the `ConfiguredNextVersion`
   strategy beside `Mainline`. Mainline alone ignores it. Write it with the
   tag prefix (`'v0.1.0'`), because GitVersion 6.8.2 refuses a bare `0.1.0`.
3. **Pin the GitVersion engine exactly** (`versionSpec: '6.8.2'`), because
   the version it computes ends up in production. Dependabot doesn't see this
   line, so move it by hand and rerun the title table when you do.
4. **A `PR Title` check** (`.github/scripts/check_pr_title.py`) reads the
   patterns from `GitVersion.yml`, fails a title none of them reads, and says
   on the PR which bump the merge releases. It is a required check.

## The release, on every merge to main

5. One run at a time (`concurrency: release`, `cancel-in-progress: false`), on
   main only, with every job checking the ref. The steps, in order:
   1. Run the tests again on the squash commit.
   2. Determine the version, and skip the run when the image, the git tag and
      the GitHub release for it all exist.
   3. Build and push the image under the version only, with no `latest`.
      Label it with the version and the commit. Attach SBOM and provenance
      attestations (`sbom: true`, `provenance: mode=max`). Then push an
      annotated tag `v<version>`.
   4. Scan the pushed digest with Trivy before anything moves onto it (see
      [security.md](security.md)).
   5. Create the GitHub release with notes generated from the PR titles, and
      attach the SBOM to it. A release finished late must not take "Latest"
      from a newer one.
   6. Bump the deployed version: the image tag in Kubernetes-Manifests,
      edited in place on its one `newTag` line, through one fixed branch,
      force-pushed and self-merging. **Conditional (Helm chart):** also bump
      the chart's `appVersion`, after the release exists.
6. **Re-runs finish a release.** Each piece is made only when it's missing. An
   image already under the version must carry this commit's revision label,
   or the run stops. A tag that names another commit is refused, not moved.
   Read the label with `{{ json .Image }}` and jq, which works whether the
   image has one platform or several.
7. **Fix forward.** A bad release is fixed by the next one. The pipeline is
   the only way to deploy: never hand-build, hand-push or hand-edit a
   deployed tag.

## Workflow hygiene

8. Pin every action to a full commit SHA, with its version in a comment, and
   every base image as `tag@digest`. Dependabot moves both.
9. Least privilege: `permissions: contents: read` at the top of each
   workflow, with write granted per job. The only checkout that keeps its
   token is the one that pushes. Pass titles and other user input through
   `env:`, never into the shell line.
10. A `timeout-minutes` on every job, because releases queue behind each
    other.
11. Pass secrets only to the step that needs them. Never hand a token to a
    third-party action in a step that can rewrite `$GITHUB_PATH` or
    `$GITHUB_ENV` for a later step that holds a secret.

## Pull request checks

12. Every PR runs:
    - the tests, with the coverage report
    - a linter (for example ruff, ESLint) that also fails a broad `except`
      that swallows its error: it re-raises, logs its traceback, or carries
      a suppression with the reason beside it
    - a type checker for every typed language (`tsc --noEmit`, mypy)
    - hadolint on every Dockerfile
    - the `PR Title` check
    - when the project ships an image: an image build, a Trivy scan of that
      image with a sticky PR comment that rewrites on each push, and a smoke
      test of the built image
    - **conditional (web UI):** Lighthouse CI budgets and a browser smoke
      test with axe
13. **Conditional (web UI):** a preview environment per PR, and a cache
    cleanup workflow when caches pile up. A preview lives for as long as its
    PR carries a label, and ends when the label comes off or the PR closes;
    there's no age limit. Previews share one namespace, apart from
    production's, with Pod Security `restricted`.
14. Every CI check is also a `make` target that runs in Docker.
15. **Unused code is found on demand.** A `make check-unused` target (Knip,
    Vulture) runs before a refactor lands, and every allowlisted exception
    sits beside its reason.

## Delivery

16. **Conditional (Kubernetes):** GitOps through Argo CD and the
    Kubernetes-Manifests repo. Argo CD auto-syncs and reverts changes made
    outside git. The version is pinned in git, and the release is the only
    thing that bumps it.
17. **Conditional (long-running, user-facing service on Kubernetes):**
    1. A Helm chart instead of hand-written manifests, inflated through
       Kustomize's `helmCharts` generator.
    2. Argo CD finds it through an ApplicationSet with a Git generator.
    3. The ApplicationSets and AppProjects are managed by the app-of-apps
       pattern from the root Application.
    4. The chart is published to ArtifactHub with full documentation.
    5. The service deploys through Argo Rollouts with a canary or blue-green
       strategy, and a gate that checks the new version before it takes the
       traffic. The gate exercises only the service and what it deploys with,
       never a third party, so an outside outage can't fail or block a good
       release.
18. **Conditional (a cloud: AWS, Cloudflare and so on):** Terraform for
    every resource. No ClickOps, and no one-off API calls.
