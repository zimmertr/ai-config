# APIs and services

Every section but Logs is conditional, and applies when the interview
switches it on.

## The API contract

**Conditional (API).**

1. **The OpenAPI document is committed.** CI regenerates it and fails on a
   diff, so a contract change shows up in review. A `make` target regenerates
   it.
2. **A strict reader.** Request models refuse unknown fields
   (`extra="forbid"` in Pydantic), every nested model included, and every
   list in a request carries a `maxItems`. Response fields are all marked
   required, because the server always sends them, and new ones are
   additive.
3. **What the version promises.** From 1.0, SemVer covers the documented
   routes and their statuses, every request and response field, the error
   object, and any URL parameters a link carries. It doesn't cover message
   wording. `docs/API.md` says so.
4. **A client in another language generates its types** from the committed
   document, and the typecheck holds its hand-written types against them,
   so one contract change lands on both sides in one PR.

## Errors

**Conditional (API).**

5. **One error shape.** Every failure answers one body, with a stable code a
   caller can branch on and a flag saying whether a retry can help. An
   unhandled exception is caught by the innermost middleware, logged with its
   traceback, and answered as `internal`, so it leaves with every security and
   CORS header and its text never reaches the caller.

## Limits

**Conditional (API).**

6. **Requests are bounded before they're read.** A body over the cap gets a
   `413` without the server reading it, and every list in a request has a
   maximum length. `docs/LIMITS.md` names every bound and why.

## Logs

Every program that logs: a scheduled job holds tokens as surely as a
service does.

7. **Redaction is a mechanism, not a habit.** One formatter on the root log
   handler masks secrets and escapes control characters in the whole record,
   traceback included, so no call site can forget. A library logger that
   prints full URLs at `INFO` is pinned at `WARNING`.

## Public services

**Conditional (public service):** reachable from the internet by people
the maintainer doesn't know.

8. **Rate limits per client.** Each client address gets its own bucket, and a
   request past its budget gets a `429` with `Retry-After`. Count an IPv6
   client by its /64, since one host can hold a whole /64.
9. **Client identity comes from the proxy that sets it.** A client-IP header
   (such as Cloudflare's `CF-Connecting-IP`) is believed only on a request
   from the proxy that sets it. The gateway strips it from every other peer,
   so a caller can't pick its own bucket.
10. **Every response carries the security headers**, errors included.
    **Conditional (browser client)** as well: a Content-Security-Policy lists
    exactly the hosts the client reaches, beside the standard headers
    (`nosniff`, `frame-ancestors`, a referrer policy). A test reads the
    client's source and fails on a host the policy hasn't classified, so a new
    host can't ship unlisted. HSTS goes wherever TLS ends.
