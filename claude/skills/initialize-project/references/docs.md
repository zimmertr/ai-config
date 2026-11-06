# Documentation

1. Keep detailed documentation from the first PR. It is written for humans
   and AI agents alike.
2. Write it so an agent can find how part of the service behaves, and where
   that part is defined, without loading the whole codebase.
3. A change that makes any page untrue updates it in the same PR.

## CLAUDE.md

4. The root `CLAUDE.md` is short: what the project is, a table of every doc
   and the topic it owns, the rules that hold for every change (each linked
   to its ADR), and an "Issues" section for `create-issue`.
5. A large codebase adds a nested `CLAUDE.md` per source directory, listing
   each module, what it owns, and why it's separate. A new module gets its
   line in the same PR.

## The docs/ set

6. Every project has the pages below that apply to it, under `docs/`:

| File | Holds |
|---|---|
| `architectural-decision-records/` | One ADR per decision, with `README.md` as the index and `0000-template.md` |
| `API.md` | How to call the API, and what its version promises. **Conditional (API)** |
| `ARCHITECTURE.md` | Diagrams and the overall design: components, flows, modules, deployed objects |
| `CICD.md` | How a change gets from a PR to production, with a diagram, and every secret |
| `CONFIGURATION.md` | Every CLI flag, environment variable and setting, and where each is set |
| `DATA.md` | Each upstream data provider, what it returns, its quirks (dated), and its licensing terms |
| `DEVELOPMENT.md` | The CI-first loop, the Docker commands, how to write tests, fake data |
| `LIMITS.md` | Every cap, timeout and size bound, and why. A number the service publishes is described and pointed at, never restated (see [service.md](service.md)) |
| `SBOM.md` | Where the software bill of materials is and how it's made (see below) |
| `STYLES.md` | UI patterns, framework, design tokens and copy rules. **Conditional (UI)** |
| `TRAFFIC.md` | How traffic flows into and through the project, every outbound call with its timeout and retries, and, for a public service, the rate limits and where client identity comes from |
| `USAGE.md` | What the user sees, and what to do when it breaks |

## Architectural decision records

7. Every decision gets an ADR in the same PR that makes it, and the
   CLAUDE.md rule that states the decision links to it right after the
   sentence, as ` Record: [NNNN](docs/architectural-decision-records/NNNN-slug.md)`.
8. **Naming:** `docs/architectural-decision-records/NNNN-slug.md`. `NNNN` is
   four digits, the next free number, never reused. The slug is the decision
   in a few lowercase words joined by hyphens, for example
   `0021-semver-release-per-merge.md`.
9. **Format:** copy [../templates/0000-template.md](../templates/0000-template.md).
   The title is the decision, as one sentence. Then:
   - Status, date, decider (quoting the decider's words where they exist),
     the issues and PRs, the numbers source comments cite it under, and the
     guide section that states it today
   - **Context**: what forced a choice
   - **Decision**: what was chosen, so a reader can check the code against it
   - **Evidence**: the measurements that settled it, each dated
   - **Alternatives rejected**, and why each lost
   - **Consequences**: what holds the decision in place, and what it costs
10. **Superseding:** a new record that reverses an old one says
    `Supersedes NNNN` in its status line. The old record changes its status
    line and nothing else.
11. The index, `README.md`, starts from [../templates/README.md](../templates/README.md):
    how to write a record, and a table of every record, with its date and
    status.

## The SBOM

12. The SBOM is generated, never written by hand. Every release makes one for
    the image it ships (BuildKit's `sbom: true` attestation, and an SPDX or
    CycloneDX JSON file attached to the GitHub release). It lists every
    dependency with its version, supplier, license and checksum.
13. `docs/SBOM.md` says where to find the SBOM (the latest release's asset,
    and `docker buildx imagetools inspect --format '{{ json .SBOM }}'` on the
    image), how CI makes it, and which licenses need attention.
