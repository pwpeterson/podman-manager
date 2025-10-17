# Enhanced Delegation Examples

## Code Quality Review

**Scenario**: User: "Review this authentication module for security issues"

**Process**:
1. Inform: "Delegating security analysis to local Qwen2.5-Coder..."
2. Use security_scan_code with vulnerability focus on authentication/authorization
3. Use generate_code_review with security focus
4. Review findings, add context-specific recommendations
5. Present: "Security analysis completed with local LLM, findings reviewed and verified"

## Performance Optimization

**Scenario**: User: "This function is running slowly, can you optimize it?"

**Process**:
1. Use generate_performance_analysis for bottleneck identification
2. Inform: "Delegating performance analysis to local Qwen2.5-Coder..."
3. Handle complex optimizations directly based on LLM recommendations
4. Use generate_tests to verify optimizations don't break functionality
5. Present: "Performance analysis with local LLM, optimizations implemented and tested"

## Type Safety Enhancement

**Scenario**: User: "Add type hints to this Python module"

**Process**:
1. Inform: "Delegating type annotation generation to local Qwen2.5-Coder..."
2. Use add_type_annotations with comprehensive style
3. Use optimize_imports to clean up any new imports
4. Use precommit&fix to ensure style compliance
5. Present: "Type annotations generated with local LLM, imports optimized, style validated"

## Full Feature Development

**Scenario**: User: "Build a REST API endpoint for user management"

**Process**:
1. Inform: "Delegating schema and boilerplate generation to local Qwen2.5-Coder..."
2. Delegate: generate_schema for User model, generate_boilerplate_file for endpoint structure
3. Use generate_api_documentation for OpenAPI specs
4. Handle directly: business logic, authentication integration, error handling
5. Use security_scan_code to validate final implementation
6. Use git_smart_commit for version control
7. Present: "Schema and boilerplate generated with local LLM, business logic implemented directly, security validated"

## Project Quality Audit

**Scenario**: User: "Audit this codebase for quality issues"

**Process**:
1. Use analyze_codebase for high-level assessment
2. Use suggest_refactoring_opportunities for specific improvements
3. Use security_scan_code for vulnerability assessment
4. Use precommit for current style compliance
5. Compile comprehensive quality report with prioritized recommendations
6. Present: "Quality audit completed using local LLM analysis tools, comprehensive report generated"

## Key Principles

**MUST** inform user before delegating any task

**MUST** always review and improve delegated output

**MUST** mention delegation in completion summary

**SHOULD** combine delegation with direct implementation for complex features

**SHOULD** use multiple vLLM tools in sequence for comprehensive analysis
