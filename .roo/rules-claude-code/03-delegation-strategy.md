# Task Delegation Strategy

## Delegation Workflow

**MUST** analyze task complexity and context requirements before delegating

**MUST** inform user before delegating: "Delegating [task] to local Qwen2.5-Coder..."

**MUST** always review delegated output for:
- Correctness and completeness
- Code style consistency with project patterns
- Edge cases and error handling
- Integration with existing codebase

**MUST** make necessary improvements before presenting to user

**MUST** mention briefly on completion: "Generated with local LLM, reviewed and verified"

## When to ALWAYS Delegate to Local vLLM

### Code Generation
- **MUST** delegate boilerplate code generation (CRUD operations, basic models, standard endpoints)
- **MUST** delegate simple utility functions with clear, single-purpose logic
- Repetitive code patterns (similar functions with minor variations)
- Basic test fixtures and simple test cases
- Standard implementations (getters/setters, simple parsers, formatters)
- Code completions for straightforward function bodies
- Documentation generation (docstrings in any style)
- Git commit messages and PR descriptions
- Configuration files (.gitignore, GitHub workflows, Dockerfiles)
- Basic refactoring (variable renaming, extract method, simplify conditionals)
- Format conversions (camelCase↔snake_case, JSON↔YAML)
- Schema generation (Pydantic, SQLAlchemy, GraphQL, TypeScript)
- SQL query generation for common CRUD operations
- Quick code explanations for simple snippets
- Code reviews of individual functions or files
- Security scanning for common vulnerabilities
- Performance analysis of isolated code sections
- Type annotation addition to existing code
- Import optimization and cleanup
- Simple file edits (line length fixes, formatting corrections, style improvements)
- Code style fixes identified by linters (flake8, eslint, etc.)
- Automated code corrections from precommit hooks
- Single-file refactoring (within same file boundaries)
- Adding/removing imports based on usage analysis

## Never Delegate - Handle Directly

- Architectural decisions and system design
- Complex algorithms requiring optimization
- Security-sensitive code (authentication, authorization, encryption)
- Code requiring deep project context from ConPort
- Error handling strategies for production systems
- Performance-critical code optimization
- Complex refactoring spanning multiple files
- Integration code connecting multiple systems
- Code reviews requiring design pattern judgment
- Debugging complex logic errors, race conditions, memory issues

## Performance Notes

- Local LLM responses typically take 3-8 seconds for the 32B model
- Use health_check to verify vLLM availability before heavy delegation
- Delegate simple, isolated tasks to vLLM for 2-5x speed improvement
