# Done: the checklist and the outputs

The foundation is done when every line below is checked against the live repo
and its runs, not against the plan. Reading the workflow file is not checking
that the workflow ran. `O/R` is the repo's owner and name.

Each line ends in one of three marks, and the report carries all three:

- **done**, with the evidence: a command's output, a run, a link
- **n/a**, with the interview answer that switched it off
- **blocked**, with what's missing and who can unblock it.

## Repo and settings

The settings lines check what yggdrasil's apply set: the repo's file is in
its `repos/<owner>/`, that PR's apply succeeded, and the next plan on
yggdrasil's main shows no change for the repo. When a line is wrong, fix the
repo's file in yggdrasil, not the setting.

1. The files from [repo.md](repo.md) exist: `LICENSE`, `.gitignore`,
   `.dockerignore`, `README.md`, `NOTICES.md` (when needed) and
   `CLAUDE.md`. There is no `SECURITY.md`, `CONTRIBUTING.md` or
   `.github/ISSUE_TEMPLATE/`, so the owner's shared ones apply.
2. The icon from [repo.md](repo.md) is the maintainer's pick from the ten
   options, reads at 16 px with no parts touching, and is one SVG. The
   README's top points at that file, and so do the favicon, the header mark
   and the chart's `icon:` wherever the project has them.
3. `docs/social-preview.png` is 1280x640, its source is committed beside
   it, its subtitle matches `gh repo view O/R --json description` word for
   word, and it is uploaded:
   `gh api graphql -f query='{repository(owner:"O",name:"R"){usesCustomOpenGraphImage openGraphImageUrl}}'`
   returns `usesCustomOpenGraphImage: true`. No API or Terraform setting
   uploads it, so until the maintainer does under Settings, Social preview,
   this line is blocked on the maintainer.
4. Merge settings: `gh api repos/O/R` shows squash only, `PR_TITLE` and
   `PR_BODY`, auto-merge, branch deletion and "Update branch" on, and the
   wiki off.
5. Branch protection: `gh api repos/O/R/rules/branches/main` shows the
   required checks from [security.md](security.md), conversation resolution,
   and no force-push or deletion, with no bypass actors.

## Security

6. `gh api repos/O/R -q .security_and_analysis` shows secret scanning and
   push protection on.
7. Dependabot alerts (`gh api repos/O/R/vulnerability-alerts` answers 204),
   security updates, and private vulnerability reporting are on.
8. CodeQL default setup is configured for every language, `actions`
   included (`gh api repos/O/R/code-scanning/default-setup`).
9. Immutable releases are on (`gh api repos/O/R/immutable-releases`), and
   every deploy pins its image by digest.
10. `.github/renovate.json` extends yggdrasil's preset, and Renovate's first
   PR below a major armed auto-merge and merged itself. Until Renovate opens
   one, this line is blocked on Renovate, and the report says so.

11. The dependency-lock test exists and passed on a PR, and a grep of the
   Dockerfile, the Makefile and the workflows confirms `--ignore-scripts` on
   every `npm ci` and `--require-hashes` on the image's `pip install`.

## CI/CD

12. A PR ran every check in [cicd.md](cicd.md), each one required, and all
   passed. Every workflow calls yggdrasil's modules pinned by SHA, and none
   copies one. The coverage report is on the PR, and every gap below 100% has
   a test or a written reason.
13. The release caller grants `packages: write`, and its first run on main
    started: a run GitHub refused to start shows `startup_failure` in the
    Actions tab while the PR looks green.
14. The PR Title check refused a title no pattern reads. Try one on a draft
    PR, then fix it.
15. The first merge to main cut the first version end to end: the image on
    GHCR under that version with its revision label and SBOM attestation, the
    Trivy scan of each platform, the tag, and the immutable GitHub release.
    The new package is public.
16. Re-running that release released nothing, and its `Version` job says
    why.
17. The weekly image scan ran once on `workflow_dispatch` and its SARIF is in
    the Security tab.
18. Every CI check runs from its `make` target in Docker.

## Docs

19. Every page from [docs.md](docs.md) that applies exists, and says
    something true about the project today.
20. Every relative link in every Markdown file resolves.
21. Every rule in `CLAUDE.md` that states a decision links its ADR, and the
    ADR index lists every record.
22. Every `CLAUDE.md` in the tree is listed in the root's docs table, and
    the release's image ships its license file (and serves it, when it
    serves HTTP).

## Conditional

23. **Kubernetes:** the release's bump merged in Kubernetes-Manifests, and
    Argo CD shows the app Synced and Healthy on the new version
    (`kubectl` reads are allowed; changes are not).
24. **Helm chart:** the chart is on GHCR with its README, the release
    bumped its `appVersion`, and a Rollout promoted the new version through
    its gate.
25. **Database:** the database tests ran in their own CI job, against a
    throwaway database built in the job.
26. **API:** a draft PR that changes a model without regenerating the
    OpenAPI document fails its check, and an oversized request body gets a
    `413`.
27. **Public service:** a burst past one client's bucket gets a `429` with
    `Retry-After`, a client-IP header sent from outside the proxy doesn't
    change the bucket, and every response, a `404` included, carries the
    security headers (`curl` against the project's own host).
28. **Web UI:** Lighthouse budgets, the browser smoke test with axe in every
    theme, and a PR preview all ran on a PR. A colour literal written outside
    its owning module, tried on a draft PR, fails the linter.
29. **A cloud:** `terraform plan` on main shows no changes.

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
