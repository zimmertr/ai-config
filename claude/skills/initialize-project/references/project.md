# Project principles

1. **Test-driven development, at 100%.** Tests come with the code they cover,
   in the same PR. Coverage is 100% of lines and branches, CI scripts
   included, and CI fails below it. Tests never touch the network or a real
   database. The only coverage exclusion is the `if __name__ == "__main__":`
   idiom or its equivalent; anything else that seems untestable is a design
   problem to raise.
2. **API-first design.** Start with the primitives: design the database
   first, then build an API on it. Only then build a UI or CLI that uses
   these primitives.
3. **End-to-end CI/CD from the first PR.** Set up continuous integration
   first, and continuous delivery as soon as there is something to deploy.
   See [cicd.md](cicd.md).
4. **12-factor design.** Every service follows the Twelve-Factor App
   (12factor.net): config in the environment, stateless processes, backing
   services as attached resources, logs to stdout, and the rest.
   - **Conditional: microservices.** When the interview says the project
     will grow into several services, split it into 12-factor
     microservices, each deployed on its own. Otherwise build a monolith.
     A monolith is the number of deployables; it says nothing about how
     many repos the code lives in.
   - **Conditional: an organization.** When a project is expected to become
     large and span many repos, host it in a GitHub organization of its own
     instead of the personal account.
5. **Modular code, without over-engineering.** Write a new feature so it can
   be reused, extended or inherited later, and reuse what exists before
   writing it again. But take the shortest path that meets the requirement:
   build what serves today, not a framework for tomorrow.
6. **Attribution.** Claude and other AI agents never add attribution to
   commits or PRs, or appear on GitHub as a contributor. All design and
   direction comes from the maintainer and is attributed to the maintainer, unless
   Anthropic's or another agent's licensing requires otherwise. Set
   `"attribution": false` in the repo's `.claude/settings.json` too, so it
   holds for any collaborator's session.
7. **Health and logs.** A long-running service exposes a health check that
   its orchestrator uses, and reports its version and commit (baked into the
   image at build time) at an endpoint. Logs are structured, go to stdout,
   and never carry a token, an id or personal data.
8. **Local development in Docker.** The project builds from a `Dockerfile`,
   and a `docker-compose.yml` runs it with its backing services. Every CI
   check is also a `make` target that runs in Docker, so a check that fails
   in CI can be rerun locally the same way.
