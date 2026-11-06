# Upstreams and mirrored logic

## Free, donated or rate-limited upstreams

**Conditional (metered upstream):** the project calls a third party whose
capacity is free and donated, rate-limited or paid. Bluebird's use of
Open-Meteo is the working example.

1. **Count capacity in the upstream's own unit.** If it bills weighted
   calls, every budget, pacer and estimate is written in weighted calls,
   never in HTTP requests, and every call site makes its weight visible.
   Bluebird: record 0002, after pricing spend in requests ran into
   Open-Meteo's rate limit (#180).
2. **Measure the sizes, don't choose them.** Batch size, concurrency per
   host and pacing are measured against the upstream, recorded with their
   date, and pinned (see [project.md](project.md)). Bluebird: #182 for the
   batch of 50 at four in flight, and record 0203, where Open-Meteo's own
   cap on open requests per address was read from its source after a run
   failed on 2026-10-20 although the pacers believed it was under budget.
3. **Refuse up front rather than half-spend.** Before spending, run the
   plan through the pacer; a request it would have to shed is refused with
   the number that applies, and nothing is spent. Bluebird: record 0074.
4. **Be a polite client.** Cache with a stated TTL. Parse a `429`, honour
   `Retry-After`, and treat each kind of refusal by its own rule. Send a
   `User-Agent` that names the project.
5. **Tests and mockups never spend real quota.** Tests stub the upstream
   from the fixtures module, and mockups run on fake, fuzzed data. When
   quota runs out, wait for its reset; never route around it.
6. **Write the posture down.** `docs/DATA.md` records each provider's
   fair-use terms and limits, dated. `docs/TRAFFIC.md` lists every call
   with its weight, timeout and retries.
7. **A costly action is an explicit commit.** Conditional (UI) too: see
   [ui.md](ui.md), Behaviour.

## Logic spelled in two languages

**Conditional (mirrored logic):** a client reimplements server logic, to
work offline or to compute in the browser. Bluebird's Python and
TypeScript mirrors are the working example.

8. **Every pair is a row.** The root `CLAUDE.md` holds a table of every
   mirrored pair: both sides, and what fails if they drift. A pair nothing
   checks says so ("a comment"). A new pair joins the table in the PR that
   creates it. Bluebird: "The Python and TypeScript mirrors", after the two
   sides' variable lists disagreed for a release while each read correctly
   on its own (#380).
9. **One fixture, read by both suites.** A formula is pinned by shared test
   vectors, and a bare number or a shared sentence by a shared manifest.
   Each is one file that both suites read, never a copy per side. A script
   regenerates the manifest from the source of truth, and a test fails a
   committed manifest that differs from what the script writes. Bluebird:
   record 0042, `backend/tests/data/weather_vectors.json`,
   `mirrored_constants.json` and `backend/tests/test_mirrored_constants.py`.
