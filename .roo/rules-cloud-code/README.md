# Roo Code Rules Directory

This directory contains the modular rules for the Claude Code mode, converted from the monolithic system prompt format to the new Roo Code rules structure.

## File Organization

### Core Behavior & Identity
- **01-core-behavior.md** - Identity, role, base operations, and tool usage fundamentals
- **02-response-format.md** - Communication style, code linking, task completion patterns

### Task Management & Delegation
- **03-delegation-strategy.md** - vLLM delegation rules, workflow, and performance guidelines
- **09-workflow-process.md** - 4-step workflow process and optimization strategies
- **10-delegation-examples.md** - Real-world delegation scenarios with detailed processes

### Technical Operations
- **04-file-operations.md** - File reading, writing, editing, and command execution rules
- **05-git-workflow.md** - Git operations, auto-staging, and version control best practices
- **07-code-quality.md** - Quality assurance workflow, analysis tools, and validation processes

### Integration & Standards
- **06-conport-integration.md** - ConPort memory system integration and logging strategies
- **08-preferred-libraries.md** - Standard libraries (loguru, rich) and implementation patterns
- **11-mcp-servers-reference.md** - Comprehensive MCP servers and tools reference

## Key Benefits of This Structure

1. **Modular Organization** - Each file focuses on a specific aspect of behavior
2. **Easy Maintenance** - Update individual rules without affecting others
3. **Clear Hierarchy** - Numbered files indicate processing priority
4. **Focused Context** - AI can load relevant rules based on task type
5. **Better Documentation** - Each rule file is self-contained and well-documented

## Usage with Roo Code

Roo Code will recursively read all markdown files in this directory and apply the rules during code mode operations. The numbered prefixes ensure important core behaviors are processed first.

## Migration Notes

This structure replaces the monolithic `.roo/system-prompt-claude-code` file with a more maintainable and organized approach that follows Roo Code best practices for rule management.
