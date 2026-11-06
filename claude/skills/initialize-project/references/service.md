# APIs and services

**Conditional:** each section applies when the interview switches it on.
Bluebird's backend (`backend/app/`) is the working example for all of them.

## The API contract

**Conditional (API).**

1. **The OpenAPI document is committed.** CI regenerates it and fails on a
   diff, so a contract change shows up in review. A `make` target
   regenerates it. Bluebird: record 0076, and its "Regenerate the OpenAPI
   snapshot" rule.
2. **A strict reader.** Request models refuse unknown fields
   (`extra="forbid"` in Pydantic), every nested model included, and every
   list in a request carries a `maxItems`. Response fields are all marked
   required, because the server always sends them, and new ones are
   additive.
3. **What the version promises.** From 1.0, SemVer covers the documented
   routes and their statuses, every request and response field, the error
   object, and any URL parameters a link carries. It doesn't cover message
   wording or the numbers the service publishes (see 6). `docs/API.md` says
   so.
4. **A client in another language generates its types** from the committed
   document, and the typecheck holds its hand-written types against them,
   so one contract change lands on both sides in one PR.

## Errors

**Conditional (API).**

5. **One error shape.** Every failure answers one body:
   `{detail, error: {code, retryable}}`. A caller branches on the codes it
   knows and falls back on `retryable` for the rest. An unhandled exception
   is caught by the innermost middleware, logged with its traceback, and
   answered as `internal`, so it leaves with every security and CORS header
   and its text never reaches the caller. Bluebird: record 0107.

## Limits

**Conditional (long-running service).**

6. **Limits are published, never restated.** The service publishes the
   limits a client acts on at an endpoint (Bluebird:
   `GET /api/capabilities`). Clients read them at run time and keep
   compiled values only as a fallback for before the fetch answers. No doc
   restates a published number: it describes the shape and the reason, and
   points at the endpoint. Bluebird: records 0005 and 0006, after three
   copies of one number had drifted apart.
7. **Requests are bounded before they're read.** A body over the cap gets a
   `413` without the server reading it: a declared `Content-Length` is
   refused at once, and a chunked body at the byte that passes the cap.
   `docs/LIMITS.md` names every bound and why. Bluebird: record 0097.

## Logs

**Conditional (long-running service).**

8. **Redaction is a mechanism, not a habit.** One formatter on the root
   log handler masks secrets and escapes control characters in the whole
   record, traceback included, so no call site can forget. A library
   logger that prints full URLs at `INFO` is pinned at `WARNING`.
   Bluebird: record 0102.

## Public services

**Conditional (public service):** reachable from the internet by people
the maintainer doesn't know.

9. **Rate limits per client.** Each client address gets its own bucket, and
   an IPv6 address counts as its /64, since one host can hold a whole /64.
   A request that would wait past its budget gets a `429` with
   `Retry-After`. Bluebird: record 0103.
10. **Client identity comes from the proxy that sets it.** A client-IP
    header (such as Cloudflare's `CF-Connecting-IP`) is believed only on a
    request from the proxy that sets it. The gateway strips it from every
    other peer, so a caller can't pick its own bucket. Bluebird: record
    0109.
