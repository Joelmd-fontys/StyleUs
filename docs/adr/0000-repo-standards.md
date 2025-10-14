# ADR 0000: Repository Standards

## Status
Accepted

## Context
The StyleUs AI fashion companion is entering its pre-code phase. Foundational decisions are required to create a predictable collaboration environment across engineering disciplines.

## Decision
- License the repository under MIT to promote openness and reuse.
- Adopt Conventional Commits to drive automated versioning and readable history.
- Enforce branch protection with mandatory review and passing CI before merge.
- Defer environment-specific tooling decisions until service requirements are defined.

## Consequences
- Contributors must follow the documented contribution workflow and commit format.
- Legal and product stakeholders acknowledge MIT terms before releasing source.
- Branch protection and CI rules may block merges until policies are satisfied.
- Environment strategy will be revisited in a future ADR once architecture solidifies.
