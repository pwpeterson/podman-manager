# Code Quality Rules

## Security Requirements

**MUST** use security_scan_code before commits

**MUST** scan delegated code for vulnerabilities

**MUST** validate auth implementations

**MUST NOT** commit code with CRITICAL/HIGH vulnerabilities

## Code Review Process

**MUST** use generate_code_review for comprehensive analysis

**MUST** review all vLLM-delegated code

**SHOULD** use detect_code_smells

**SHOULD** run browser audits for web projects

**SHOULD** query knowledge graph to validate API usage

**MUST** reference existing patterns from ConPort before implementing

## Refactoring Standards

**MUST** use suggest_refactoring_opportunities

**SHOULD** prioritize by impact

**MUST** maintain test coverage during refactoring

**MUST** make incremental changes

## Style and Formatting

**MUST** use precommit&fix for automated fixes

**MUST** validate style before presenting code

**MUST** limit function length (max 40 lines)

**MUST** follow project style guides

## Performance Optimization

**MUST** use generate_performance_analysis

**MUST** avoid N+1 query patterns

**MUST** use appropriate data structures

**MUST** measure before and after optimization

## Type Safety

**MUST** add type annotations to all new Python code

**SHOULD** use add_type_annotations for existing code

**MUST** use optimize_imports after adding type hints

## Testing Requirements

**MUST** write tests for all new features

**SHOULD** aim for 80%+ coverage on critical paths

**MUST** test edge cases and error conditions

## Code Quality Tools (vLLM-Delegator)

### Analysis Tools
- **generate_code_review** - Automated code review with severity filtering and focus areas
- **suggest_refactoring_opportunities** - Identify refactoring targets with priority ranking
- **generate_performance_analysis** - Performance bottleneck analysis with optimization suggestions
- **security_scan_code** - Security vulnerability detection with fix recommendations
- **detect_code_smells** - Code quality issue identification (duplications, complexity, naming)
- **analyze_codebase** - Project-wide analysis (structure, quality, patterns, dependencies)

### Enhancement Tools
- **add_type_annotations** - Add comprehensive type hints (Python, TypeScript, JavaScript)
- **optimize_imports** - Clean up imports (remove unused, sort, group, add missing)
- **improve_code_style** - Apply style guides (PEP8, Black, Airbnb, Google, Prettier)

### Validation Tools
- **precommit** - Run pre-commit validation on files (linting, formatting checks)
- **precommit&fix** - Auto-correct validation issues using LLM analysis

## Quality Workflow Process

1. **MUST** use security_scan_code for security reviews before commits
2. **SHOULD** use generate_code_review for comprehensive code analysis
3. **SHOULD** use suggest_refactoring_opportunities to identify technical debt
4. **SHOULD** use precommit&fix for automated code style fixes
5. **SHOULD** use generate_performance_analysis for optimization opportunities

## Multi-file Analysis

**SHOULD** read up to 5 files simultaneously for context

**SHOULD** use search_files to find patterns across codebase

**SHOULD** leverage ConPort's semantic_search for conceptual queries

**MUST** check linked decisions when making related changes

**SHOULD** use analyze_codebase for project-wide insights
