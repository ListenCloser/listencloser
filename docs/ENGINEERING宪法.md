# Engineering Constitution

## Core Principle
Minimize long-term engineering cost. Every decision optimizes for:
1. Simplicity > 2. Maintainability > 3. Correctness > 4. Testability

## Architecture Rules
- **Library = Single Source of Truth** for all track state
- Every feature derives state from the unified asset model
- Dependencies point inward; high-level never depends on implementation
- Feature-based organization, not giant utility folders

## Code Rules
- Every module has exactly one responsibility
- No silent exception swallowing
- Structured errors: `{ code, message, details }`
- Document WHY, not WHAT
- Delete dead code aggressively
- Never preserve legacy code solely because it exists

## Testing Rules
- Every bug fix gets a regression test
- Tests verify behavior, not implementation
- E2E tests cover real user flows, not just navigation
- Backend tests verify API contracts

## Deployment Rules
- Automated CI/CD
- Every PR must pass: build, lint, typecheck, tests, security scan
- No manual production steps
