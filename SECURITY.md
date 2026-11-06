# Security Policy

## Supported Versions

There are no versions. `main` is what my sessions load, and a fix ships as the next merge.

## Reporting a Vulnerability

Please report vulnerabilities privately through GitHub:
[Report a vulnerability](https://github.com/zimmertr/ai-config/security/advisories/new).
Do not open a public issue for security problems.

Include what you found, where it lives (file or workflow), and how to reproduce it.

What to expect:

- **Acknowledgement** within a few days. This is a one-person project, so response times are best effort.
- **Fix**: a confirmed vulnerability is fixed in the next merge.
- **Credit** in the advisory, unless you'd rather not.

## Scope

In scope: the skills, `claude/settings.json`, `claude/CLAUDE.md` and the CI workflows. A committed secret is the likeliest finding.

Out of scope: Claude Code itself and the plugins and tools these settings reference. Report issues in those to their maintainers.

There is no bounty program. Reports are still appreciated.
