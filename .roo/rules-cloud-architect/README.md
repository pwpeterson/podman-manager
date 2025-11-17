# Roo Architect Rules Directory

This directory contains the modular rules for the Claude Architect mode, converted from the monolithic system prompt format to the new Roo Code rules structure.

## File Organization

### Core Behavior & Identity
- **01-core-behavior.md** - Identity, role, strategic thinking principles, and file restrictions
- **02-response-format.md** - Communication style, visual documentation, and diagram best practices

### Analysis & Research
- **03-analysis-research.md** - File analysis tools, command execution, external research methods
- **08-mcp-servers-reference.md** - Comprehensive MCP servers and tools reference for architecture work

### Project Memory & Documentation
- **04-conport-integration.md** - ConPort memory system integration and decision logging strategies
- **06-decision-quality.md** - Decision-making principles, technology evaluation, and risk assessment

### Workflow & Process
- **05-architectural-workflow.md** - 4-phase architectural workflow (Discovery, Design, Planning, Handoff)
- **07-communication-collaboration.md** - Communication principles, stakeholder management, and knowledge sharing

### Advanced Techniques
- **09-advanced-techniques.md** - Complex system analysis, performance architecture, security, and technical debt management

## Key Benefits of This Structure

1. **Modular Organization** - Each file focuses on a specific aspect of architectural work
2. **Easy Maintenance** - Update individual rules without affecting others
3. **Clear Hierarchy** - Numbered files indicate processing priority
4. **Focused Context** - AI can load relevant rules based on task type
5. **Better Documentation** - Each rule file is self-contained and well-documented

## Architectural Focus Areas

### Decision Logging (Primary)
- Every architectural decision MUST be logged to ConPort
- Include summary, rationale, implementation details, and tags
- Build knowledge graph by linking related decisions

### Research-Driven Design
- Use external research servers (crawl4ai-rag, context7, brave-search)
- Analyze existing codebases and patterns
- Evaluate multiple alternatives before deciding

### Strategic Planning
- Think long-term about maintainability and evolution
- Consider security, performance, and operational concerns
- Document risks and mitigation strategies

### Comprehensive Documentation
- Create visual diagrams with Mermaid
- Document trade-offs and alternatives considered
- Provide implementation roadmaps with clear phases

## Usage with Roo Code

Roo Code will recursively read all markdown files in this directory and apply the rules during architect mode operations. The numbered prefixes ensure important core behaviors are processed first.

## Migration Notes

This structure replaces the monolithic `.roo/system-prompt-claude-architect` file with a more maintainable and organized approach that follows Roo Code best practices for rule management.

## Key Differences from Code Mode

- **No Code Implementation** - Architect mode only creates plans and documentation
- **Decision-Centric** - Every significant choice must be logged to ConPort
- **Research-Heavy** - Extensive use of external research tools
- **Visual Documentation** - Heavy use of Mermaid diagrams
- **Strategic Focus** - Long-term thinking and trade-off analysis
- **Handoff Process** - Clear transition to Code mode for implementation
