# The interview's choices

The PRD interview asks about each of these. Ask; never assume an answer. Each
answer switches standards on or off, and the PRD records every one.

| Ask | What a yes switches on |
|---|---|
| Who uses it, and how: people in a browser, a CLI, a job, other services? | A browser UI switches on [ui.md](ui.md), `docs/STYLES.md` and Lighthouse CI. An API switches on `docs/API.md` and the API contract, errors and limits sections of [service.md](service.md) |
| Will people the maintainer doesn't know reach it from the internet? | The public-service section of [service.md](service.md): per-client rate limits, client identity only from the proxy that sets it, and, with a browser client, the security headers |
| Will it grow into several services, or stay one? | Several: 12-factor microservices, each its own deployable (see [project.md](project.md)). One: a monolith, still 12-factor |
| One repo or several? | Several repos, or a project expected to become large: a GitHub organization of its own instead of the personal account |
| Where does it run: the Kubernetes cluster, a cloud (AWS, Cloudflare), or nowhere? | Kubernetes: GitOps through Argo CD and Kubernetes-Manifests. A cloud: Terraform for every resource |
| Is it a long-running, user-facing service? | A Helm chart published to ArtifactHub, an Argo CD ApplicationSet, Argo Rollouts with a canary or blue-green gate, and the release bumping the chart's `appVersion` (see [cicd.md](cicd.md)) |
| Does it keep state in a database? | Tests of the SQL against a throwaway database in a container, with their own marker, `make` target and CI job (see [project.md](project.md)) |
| Does it ship a container image? | The full image pipeline: PR-time build and scan, release scan, weekly re-scan, attestations (see [cicd.md](cicd.md), [security.md](security.md)) |
| Which license? Noncommercial/source-available, copyleft, or permissive | The `LICENSE` file, and a `NOTICES.md` when third parties need credit |
| Public or private? | Public: GitHub's free security features (see [security.md](security.md)) |
| Which upstream data or services does it depend on? | `docs/DATA.md`, with each provider's licensing terms |

When an answer is "not yet" (a UI later, a second service later), record it in
the PRD. Build what serves today, so it can be switched on later.
