---
alwaysApply: true
description: Core development rules and best practices for Diplomacy implementation
---

# Development Rules and Best Practices

For architecture overview, see [CODEBASE_OVERVIEW.md](mdc:CODEBASE_OVERVIEW.md).

## Critical Policies

**Map File Backup Policy**: When modifying map files ([standard.svg](mdc:new_implementation/maps/standard.svg), [svg.dtd](mdc:new_implementation/maps/svg.dtd)), ALWAYS create timestamped backups: `cp maps/standard.svg maps/standard_backup_$(date +%Y%m%d_%H%M%S).svg`. Fix original files directly—never change file path references in code. **CRITICAL**: Always overwrite original files, never create new names like `standard_fixed.svg` for production.

**Remote Service Deployment**: CRITICAL - Services run on a remote instance, not locally. Local curl tests to `localhost:8000` will fail. The Telegram bot connects to the remote API server. When debugging button/API issues, remember the server is deployed elsewhere.

**Never Modify Old Implementation**: NEVER make modifications to [/old_implementation/](mdc:old_implementation/). Work only in [/new_implementation/](mdc:new_implementation/).

## Code Quality Standards

- **Python Only**: All code must be Python with strict type hints
- **Ruff Compliance**: Code must pass Ruff linting and formatting
- **Full Implementations**: NO placeholders, stubs, or minimal implementations—implement fully
- **Single Source of Truth**: Avoid migrations/adapters. Implement production-quality solutions directly
- **No Backwards Compatibility**: Breaking changes are acceptable; database can be dropped if needed

## Development Workflow

### Before Starting
1. Study [specs/](mdc:new_implementation/specs/) to understand specifications
2. Review [fix_plan.md](mdc:new_implementation/specs/fix_plan.md) for current priorities
3. Understand game rules: [diplomacy_rules.md](mdc:new_implementation/specs/diplomacy_rules.md)
4. Source code location: [src/](mdc:new_implementation/src/)

### Implementation Process
1. Implement missing server functionality in Python
2. Run tests after every change: [tests/](mdc:new_implementation/tests/)
3. Fix ALL test failures (even unrelated ones)
4. Update [fix_plan.md](mdc:new_implementation/specs/fix_plan.md) when starting/resolving issues
5. Keep [requirements.txt](mdc:new_implementation/requirements.txt) updated

### Testing Requirements
- Test specifications: [testing_and_validation.md](mdc:new_implementation/specs/testing_and_validation.md)
- Tests located in [tests/](mdc:new_implementation/tests/) next to source code
- Start with testing primitives when implementing new features
- All tests must pass before committing

## Git Workflow

1. Update [fix_plan.md](mdc:new_implementation/specs/fix_plan.md) when tests pass
2. Stage changes: `git add -A`
3. Commit with descriptive message describing changes
4. Push: `git push`
5. Create version tag when all tests pass: `git tag -l | grep "^v" | sort -V` (use 'v' prefix, e.g., v1.0.2)

## Documentation Standards

- **fix_plan.md**: Update immediately when discovering, starting, or resolving issues. Remove completed items regularly. Keep up-to-date with learnings.
- **AGENT.md** (this file): Only brief operational learnings (e.g., correct commands after trial/error). NO status reports.
- **Documentation**: Capture "why" tests and implementation matter, not just "what"
- **Module READMEs**: Each module folder should have a README.md documenting the code library

## Environment Setup

- Use virtual environment: `new_implementation/venv`
- Create if missing: `python3 -m venv new_implementation/venv`
- Install dependencies: `pip install -r new_implementation/requirements.txt`

## Operational Guidelines

- Ask minimal confirmations—keep working autonomously
- Add logging when needed for debugging
- When bugs are discovered (even unrelated), resolve them after documenting in [fix_plan.md](mdc:new_implementation/specs/fix_plan.md)
- Periodically clean completed items from [fix_plan.md](mdc:new_implementation/specs/fix_plan.md) when it becomes large
