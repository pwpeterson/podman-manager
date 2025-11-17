# Code Review Checklist

## MUST Review For

### Security (CRITICAL Priority)
- **MUST** check for SQL injection
- **MUST** check for XSS vulnerabilities
- **MUST** verify authentication/authorization
- **MUST** check for sensitive data exposure
- **MUST** verify input validation
- **MUST** check for insecure dependencies
- **MUST** verify error handling (no sensitive info)
- **MUST** check for hardcoded secrets

### Performance (HIGH Priority)
- **MUST** identify N+1 query patterns
- **MUST** check for inefficient algorithms (O(n²))
- **MUST** identify potential memory leaks
- **MUST** check for blocking I/O operations
- **MUST** verify appropriate caching

### Code Quality (MEDIUM Priority)
- **MUST** check for code duplication
- **MUST** verify comprehensive error handling
- **MUST** check function complexity (max 40 lines)
- **MUST** verify naming conventions
- **MUST** check for proper logging
- **MUST** verify comments explain "why"

### Testing (MEDIUM Priority)
- **MUST** verify test coverage (80%+ for critical paths)
- **MUST** check tests are meaningful
- **MUST** verify edge cases are tested
- **MUST** check test isolation

## Review Workflow

1. **Initial Scan**
   - Use security_scan_code first
   - Use generate_code_review
   - Use detect_code_smells
   - Use generate_performance_analysis if needed

2. **Manual Review**
   - Read all changed code
   - Understand context and purpose
   - Check related code
   - Verify consistency with patterns

3. **Prioritization**
   - CRITICAL: Security vulnerabilities, data loss
   - HIGH: Performance issues, major bugs
   - MEDIUM: Code quality, maintainability
   - LOW: Style preferences, minor optimizations

4. **Feedback Generation**
   - Provide specific, actionable suggestions
   - Explain the "why"
   - Include file/line references
   - Provide code examples
   - Acknowledge good practices

5. **ConPort Integration**
   - Link findings to existing decisions
   - Log recurring issues as patterns
   - Reference similar past reviews
