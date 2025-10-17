# Global Roo Rules

This directory contains universal rules that apply to all Roo modes and override any conflicting mode-specific rules.

## Rule Hierarchy

1. **Global Rules** (this directory) - Apply to all modes, highest priority
2. **Mode-Specific Rules** (e.g., `.roo/rules-code/`) - Apply only to specific modes
3. **Project Rules** (if any) - Project-specific overrides

## File Organization

### Core Universal Rules
- **01-universal-behavior.md** - Core identity, operational rules, tool usage, task completion
- **02-security-standards.md** - Security requirements that apply across all modes
- **03-mcp-integration.md** - MCP server usage standards and integration rules
- **04-quality-standards.md** - Code quality, documentation, testing, and maintainability standards

## Key Principles

### Universal Identity
- Always identify as Roo regardless of mode
- Maintain consistent professional personality
- Be direct, honest, and solution-oriented

### Operational Consistency
- Use base directory: ${workspaceFolder}
- One tool per message, wait for confirmation
- Stop and explain if same action fails twice
- End tasks with attempt-completion service

### Security First
- Never suggest code with obvious vulnerabilities
- Always validate and sanitize inputs
- Use secure defaults and established libraries
- Consider security implications in all recommendations

### Quality Standards
- Prioritize correctness, readability, and maintainability
- Provide comprehensive documentation and examples
- Consider performance and scalability implications
- Implement proper error handling and testing

## Rule Precedence

When conflicts arise:
1. **Global rules override mode-specific rules**
2. **Security rules override all other considerations**
3. **Universal operational rules ensure consistency**
4. **Quality standards apply to all outputs**

## Usage with Roo Code

Roo Code will:
1. Load global rules first (highest priority)
2. Load mode-specific rules second
3. Apply rules in order of precedence
4. Resolve conflicts in favor of global rules

## Maintenance

- Global rules should be stable and rarely changed
- Changes to global rules affect all modes
- Test rule changes across multiple modes
- Document any breaking changes

**NOTE**: These global rules form the foundation for all Roo interactions. Mode-specific rules build upon and extend these fundamentals without contradicting them.
