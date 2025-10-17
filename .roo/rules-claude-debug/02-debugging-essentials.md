# Debugging Essentials

## Systematic Process

### Phase 1: Understand
- **MUST** define expected vs actual behavior
- **MUST** gather reproduction steps
- **MUST** determine when issue started
- **MUST** identify recent changes
- **SHOULD** assess severity
- **SHOULD** check if regression

### Phase 2: Gather Information
- **MUST** collect error messages and stack traces
- **MUST** review relevant logs
- **MUST** check system state
- **SHOULD** gather environment details
- **SHOULD** check related systems
- **SHOULD** review recent commits

### Phase 3: Form Hypotheses
- **MUST** list potential causes
- **MUST** prioritize by likelihood
- **SHOULD** consider:
  - Logic errors
  - Race conditions
  - Resource issues
  - Configuration problems
  - Dependency issues
  - Environmental differences

### Phase 4: Test Hypotheses
- **MUST** design specific tests
- **MUST** test one at a time
- **MUST** document results
- **SHOULD** use binary search
- **SHOULD** add strategic logging
- **SHOULD** use debugger breakpoints

### Phase 5: Isolate Root Cause
- **MUST** reproduce reliably
- **MUST** create minimal reproduction
- **MUST** identify exact line/component
- **SHOULD** understand why (not just where)

### Phase 6: Implement Fix
- **MUST** fix root cause, not symptoms
- **MUST** keep fix minimal
- **MUST** add tests to prevent regression
- **SHOULD** document in ConPort

### Phase 7: Verify Solution
- **MUST** verify fix resolves issue
- **MUST** run all tests
- **MUST** test in same environment

## Common Techniques

Git bisect for finding regressions
Strategic logging at decision points
Create minimal reproduction test cases

## ConPort Integration
- **SHOULD** log complex debugging sessions
- **SHOULD** reference similar past issues
- **SHOULD** link root cause to decisions
