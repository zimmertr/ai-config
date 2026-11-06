# Project principles

## Design

1. **API-first design.** Start with the primitives: design the database
   first, then build an API on it. Only then build a UI or CLI that uses
   these primitives.
2. **End-to-end CI/CD from the first PR.** Set up continuous integration
   first, and continuous delivery as soon as there is something to deploy.
   See [cicd.md](cicd.md).
3. **12-factor design.** Every service follows the Twelve-Factor App
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
4. **Modular code, without over-engineering.** Write a new feature so it can
   be reused, extended or inherited later, and reuse what exists before
   writing it again. But take the shortest path that meets the requirement:
   build what serves today, not a framework for tomorrow.
5. **The composition root decides nothing.** `main`, `App` and their kin wire
   modules together. Logic goes in pure modules a unit test can import,
   because logic left in the composition root can't be tested. Bluebird:
   record 0055.
6. **One home per rule.** A rule spelled in two shapes drifts, so it moves to
   one helper, and a check holds every site to that helper. Where a rule
   lives follows from what it reads: a ban on a code pattern belongs in the
   linter, and a measurement belongs in a test. Bluebird: records 0043,
   0189.
7. **Measured numbers are pinned.** A magic number (a contrast ratio, a batch
   size, a timeout) is measured, written down with its date, and asserted in
   a test, so a change forces a re-measurement. A measured constant with a
   comment beats code that computes the number at run time. Bluebird: record
   0008 and #167, where a comment claiming 4.6:1 shipped over a measured
   4.02:1.
8. **Attribution.** Claude and other AI agents never add attribution to
   commits or PRs, or appear on GitHub as a contributor. All design and
   direction comes from the maintainer and is attributed to the maintainer,
   unless Anthropic's or another agent's licensing requires otherwise. The
   maintainer's global settings set `"attribution": false`; a repo doesn't
   repeat it in its own `.claude/settings.json`.
9. **Health and logs.** A long-running service exposes a health check that
   its orchestrator uses, and reports its version and commit (baked into the
   image at build time) at an endpoint. Logs are structured, go to stdout,
   and never carry a token, an id or personal data; one redacting
   formatter holds that (see [service.md](service.md), Logs).
10. **Local development in Docker.** The project builds from a `Dockerfile`,
    and a `docker-compose.yml` runs it with its backing services. Every CI
    check is also a `make` target that runs in Docker, so a check that fails
    in CI can be rerun locally the same way.
11. **Performance before and after.** Every PR that changes shipped code or
    its build states the before and after for what it touches: a page load,
    an interaction, a request, a job's run time. A result of neither is
    measured and stated as one. A docs-only or config-only PR is exempt.
    Bluebird: record 0041, where an overlay toggle went from 1,982 ms to
    277 ms.

## Tests

12. **Test-driven development, striving for 100%.** Tests come with the code
    they cover, in the same PR. CI measures line and branch coverage, CI
    scripts included, and reports it on every PR. The aim is 100%, and every
    gap gets a test of the behaviour behind it or a written reason. The
    maintainer, 2026-11-05: "Strive for 100% coverage but don't do weird
    things to get there."
13. **Never game the number.** Every test asserts on behaviour; a test that
    only executes a line is deleted, whatever that does to the number. Code
    isn't contorted to reach a line, and nothing is excluded from coverage
    without its reason beside the exclusion. Bluebird reads coverage as an
    on-demand report with no floor (record 0187), after an audit found tests
    that ran lines without asserting anything; hevy-trainer-sync gates at
    100% (its record 0018). The rule allows either.
14. **No test touches the network, a production system, or a shared
    database.**
    - **Conditional (database):** code that speaks SQL is tested against a
      throwaway database in a container, because a fake of the database
      tests nothing about the SQL. Those tests carry a marker (`db`), have
      their own `make` target, and run in their own CI job. Bluebird:
      `make test-backend-db`, against `backend/tests/db/Dockerfile`.
15. **Fakes come from one place.** Each suite has one fixtures module that
    builds every fake: a row, an HTTP answer, an upstream stub. Tests compose
    it and never spell a fake inline. A fake HTTP answer must be able to fail
    `raise_for_status`. Bluebird: `frontend/src/testSupport/fixtures.ts`
    and `backend/tests/conftest.py`, after #389 and #439 unwound eleven
    copies of one result row.
16. **A check can't pass by finding nothing.** A test that reads files fails
    when it can't find them, instead of skipping. Every custom lint rule has
    a fixture proving it fires, and a self-test fails when one doesn't: a
    rule that matches nothing reports nothing, which looks exactly like a
    clean tree. Bluebird: record 0196, and `frontend/tools/eslint/selftest.js`.
17. **Time is fixed.** Tests pin the time zone and the clock. No test spells
    a calendar date that will pass; dates come from one helper, relative to
    the fixed start. Bluebird: record 0195.
