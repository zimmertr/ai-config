---
name: initialize-project
description: Start a new project from nothing. Interview the maintainer into a PRD, plan it as a dependency graph of tasks filed as GitHub issues under an epic, then create the repo with the standard CI/CD, security, documentation and repo settings. Use only when the maintainer runs /initialize-project.
argument-hint: "[what the project is, in a sentence or two]"
disable-model-invocation: true
---

# Initialize a project

Seed a new project with the maintainer's standards, so every project works the
same way and follows current practice for security, CI/CD and the rest of the
software development lifecycle. This skill covers a new project only.

How the agent behaves in every session (asking, scratchpad clones, Docker,
CI-first, attribution, subagents) is in the global `~/.claude/CLAUDE.md` and
is not repeated here. This skill adds the process and the standards a new
project starts with.

## The standards

Read each file when its step needs it, not all at once:

| File | Covers |
|---|---|
| [references/project.md](references/project.md) | Project principles: tests, API-first, 12-factor, attribution |
| [references/interview.md](references/interview.md) | The choices to ask about, and what each choice switches on |
| [references/cicd.md](references/cicd.md) | Release pipeline, PR checks, GitOps, Kubernetes, Terraform |
| [references/security.md](references/security.md) | Branch protection, Dependabot, scanning, secrets, reporting |
| [references/repo.md](references/repo.md) | Repo files, settings, issues, branching |
| [references/docs.md](references/docs.md) | The `docs/` set, CLAUDE.md, ADRs, the SBOM |
| [references/service.md](references/service.md) | The API contract, errors, limits, logs and public-service guards, when they apply |
| [references/upstreams.md](references/upstreams.md) | Metered upstreams, and logic spelled in two languages, when they apply |
| [references/ui.md](references/ui.md) | User interfaces, when there is one |
| [references/done.md](references/done.md) | The checklist the foundation must pass, and the report it ends in |
| [templates/](templates/) | The ADR template and the ADR index to copy in |

A standard marked **conditional** applies only when the interview switches it
on. Everything else applies to every project.

## Process

1. **Interview into a PRD.** Build the PRD from the maintainer's
   initialization prompt. Ask one question at a time, each based on the
   previous answers, and go deeper on every detail until it is well-defined
   and scoped. Cover every choice in
   [references/interview.md](references/interview.md) before the PRD is done;
   never assume an answer to one of them.
2. **Write the PRD** as an Artifact or a markdown file with at least these
   sections:
   1. Project overview
   2. Core requirements
   3. Core features
   4. Core components
   5. App/user flow
   6. Tech stack
   7. Implementation plan
   8. The interview's choices and what each one switches on
3. **Plan the build, once the PRD is signed off.** Write a detailed
   step-by-step plan to build the project. Break it into tasks that build on
   one another, then break those into smaller sub-tasks. Each step must be
   small enough to implement in one go and big enough that together they
   finish the project.
4. **Make the plan a dependency graph.** Use current development practice and
   real project management, with no large jumps in complexity. Wire sub-tasks
   into one another so no task is orphaned. Every task and sub-task is a
   checklist item with a numbered ID, and lists the IDs it depends on. Give
   each enough context that a developer or an agent can start on it at once.
   The first tasks set up the repo, CI/CD and docs, before any feature work.
5. **File the plan as GitHub issues** with the `create-issue` skill: one
   issue per task, under an epic issue that tracks them as sub-issues.
6. **Build the foundation**: the first tasks, which create the repo and set
   up its CI/CD, security and docs to the standards above. Every change
   follows the global rules: a PR that has passed CI.
7. **Check the foundation, and report.** Run every line of
   [references/done.md](references/done.md) against the live repo and its
   runs, and send the maintainer its outputs: the links, and each line's mark
   and evidence. Fix what fails before reporting. Stop here until the
   maintainer has seen the report.
8. **Build the features**, task by task, in the order of the dependency
   graph.
