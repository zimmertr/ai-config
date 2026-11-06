# Done: the checklist and the outputs

The foundation is done when every line below is checked against the live repo
and its runs, not against the plan. Reading the workflow file is not checking
that the workflow ran. `O/R` is the repo's owner and name.

Each line ends in one of three marks, and the report carries all three:

- **done**, with the evidence: a command's output, a run, a link
- **n/a**, with the interview answer that switched it off
- **blocked**, with what's missing and who can unblock it. Docker Hub's
  immutable tags are set in its web UI, so that line is often blocked on the
  maintainer.

## Repo and settings

1. The files from [repo.md](repo.md) exist: `LICENSE`, `.gitignore`,
   `.dockerignore`, `README.md`, `SECURITY.md`, `CONTRIBUTING.md`,
   `NOTICES.md` (when needed), `.github/ISSUE_TEMPLATE/` and `CLAUDE.md`.
2. Merge settings: `gh api repos/O/R` shows squash only, `PR_TITLE` and
   `PR_BODY`, auto-merge, branch deletion and "Update branch" on, and the
   wiki off.
3. Branch protection: `gh api repos/O/R/branches/main/protection` shows the
   required checks from [security.md](security.md), conversation resolution,
   admins enforced, and no force-push or deletion.

## Security

4. `gh api repos/O/R -q .security_and_analysis` shows secret scanning and
   push protection on.
5. Dependabot alerts (`gh api repos/O/R/vulnerability-alerts` answers 204),
   security updates, and private vulnerability reporting are on.
6. CodeQL default setup is configured for every language, `actions`
   included (`gh api repos/O/R/code-scanning/default-setup`).
7. Immutable releases are on (`gh api repos/O/R/immutable-releases`), and so
   are immutable tags on the image registry.
8. The `AUTO_MERGE_PAT` Dependabot secret exists
   (`gh api repos/O/R/dependabot/secrets`), and Dependabot's first patch or
   minor PR armed auto-merge and merged itself. Until Dependabot opens one,
   this line is blocked on Dependabot, and the report says so.

9. The dependency-lock test exists and passed on a PR, and a grep of the
   Dockerfile, the Makefile and the workflows confirms `--ignore-scripts` on
   every `npm ci` and `--require-hashes` on the image's `pip install`.

## CI/CD

10. A PR ran every check in [cicd.md](cicd.md), each one required, and all
   passed. The coverage report is on the PR, and every gap below 100% has
   a test or a written reason.
11. Deleting one lint fixture on a draft PR fails the lint self-test, and
    hiding a file a policy test reads fails that test instead of skipping it.
12. The PR Title check refused a title no pattern reads. Try one on a draft
    PR, then fix it.
13. The first merge to main cut the first version end to end: the tag, the
    image under that version with its revision label, the Trivy scan of its
    digest, and the immutable GitHub release with its SBOM attached.
14. Re-running that release changed nothing: every piece was skipped as
    already there.
15. The weekly image scan ran once on `workflow_dispatch` and its SARIF is in
    the Security tab.
16. Every CI check runs from its `make` target in Docker.

## Docs

17. Every page from [docs.md](docs.md) that applies exists, and says
    something true about the project today.
18. Every relative link in every Markdown file resolves.
19. Every rule in `CLAUDE.md` that states a decision links its ADR, and the
    ADR index lists every record.
20. Every `CLAUDE.md` in the tree is listed in the root's docs table, and
    the release's image ships its license file (and serves it, when it
    serves HTTP).

## Conditional

21. **Kubernetes:** the release's bump merged in Kubernetes-Manifests, and
    Argo CD shows the app Synced and Healthy on the new version
    (`kubectl` reads are allowed; changes are not).
22. **Helm chart:** the chart is on ArtifactHub with its docs, the release
    bumped its `appVersion`, and a Rollout promoted the new version through
    its gate.
23. **Database:** the database tests ran in their own CI job, against a
    throwaway database built in the job.
24. **API:** a draft PR that changes a model without regenerating the
    OpenAPI document fails its check, and an oversized request body gets a
    `413`.
25. **Mirrored logic:** every pair in the code is a row in the mirror table.
    On a draft PR, changing one side's logic alone fails its suite against
    the shared fixture, and editing the manifest by hand fails the
    staleness test.
26. **Public service:** a burst past one client's bucket gets a `429` with
    `Retry-After`, a client-IP header sent from outside the proxy doesn't
    change the bucket, and every response, a `404` included, carries the
    security headers (`curl` against the project's own host).
27. **Web UI:** Lighthouse budgets, the browser smoke test with axe in every
    theme, and a PR preview all ran on a PR. A colour literal written outside
    its owning module, tried on a draft PR, fails the linter.
28. **A cloud:** `terraform plan` on main shows no changes.

## The outputs

When every line is done or n/a, report to the maintainer, with links:

1. The PRD.
2. The epic issue, its sub-issues, and which task comes next.
3. The repo, and the first PR that passed every check.
4. The first release: version, tag, image digest, scan result.
5. **Conditional (Kubernetes):** the deployed version, and its Argo CD state.
6. The checklist above with every line's mark and evidence, blocked lines
   first.

Feature work starts only after the maintainer has seen that report.
