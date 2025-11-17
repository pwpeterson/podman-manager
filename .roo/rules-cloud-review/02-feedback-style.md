# Feedback Style Guidelines

## Communication Principles

- **MUST** be constructive and professional
- **MUST** explain reasoning behind suggestions
- **MUST** provide specific examples
- **SHOULD** acknowledge good practices
- **SHOULD** frame as learning opportunities
- **AVOID** personal criticism

## Feedback Format

### Severity Levels
- **CRITICAL**: Security vulnerabilities, data loss, production-breaking
- **HIGH**: Significant bugs, performance problems
- **MEDIUM**: Code quality, maintainability, minor bugs
- **LOW**: Style preferences, small optimizations

### Structure
Each finding should include:
1. **Severity**: CRITICAL / HIGH / MEDIUM / LOW
2. **Location**: File path and line number(s)
3. **Issue**: Clear description
4. **Impact**: Why this matters
5. **Suggestion**: Specific, actionable fix with code example
6. **Reasoning**: Educational explanation

## Example Good Feedback

MEDIUM - src/auth.py:45-120

Issue: The authenticate_user() function is 75 lines long, exceeding the 40-line guideline.

Impact: Long functions are harder to test, debug, and maintain. This function handles validation, database queries, and response formatting - mixing multiple concerns.

Suggestion: Extract into smaller, focused functions

Reasoning: Single Responsibility Principle - each function should have one clear purpose. This makes code more testable and maintainable.

## Mentoring Approach

- **SHOULD** explain security implications
- **SHOULD** suggest learning resources
- **SHOULD** highlight reusable patterns
- **SHOULD** connect to broader principles

## Tone Guidelines

Good: "Consider extracting this into a separate function for better testability"
Bad: "This is wrong, you should know better"

Good: "Great error handling here! Consider applying this pattern to..."
Bad: "Finally, something done right"
