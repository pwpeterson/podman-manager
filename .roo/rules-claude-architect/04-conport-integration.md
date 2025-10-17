# ConPort Memory Integration Rules

## Initialization on First Message

**MUST** follow this sequence:
1. Get workspace_id from ${workspaceFolder}
2. Check for context_portal/context.db
3. If database exists:
   - Load: get_product_context, get_active_context
   - Load: get_decisions(limit:5), get_system_patterns(limit:5)
   - Set status: [CONPORT_ACTIVE]
   - Options: Continue previous planning? Review decisions? New architecture task?
4. If no database:
   - Ask: Initialize ConPort for architectural documentation?
   - Set status: [CONPORT_ACTIVE] or [CONPORT_INACTIVE]

## Status Indicator

**MUST** begin every response with [CONPORT_ACTIVE] or [CONPORT_INACTIVE]

## Decision Logging (Primary Tool)

**MUST** log every architectural decision using log_decision with:
- **Required**: summary (concise decision statement)
- **Critical**: rationale (why this approach was chosen)
- **Important**: implementation_details (how it will be implemented)
- **Optional**: tags (for categorization and discovery)

### Document Decision Process

**MUST** document in ConPort with:
- Problem statement
- Considered alternatives
- Chosen solution
- Rationale
- Trade-offs
- Risks and mitigations

## When to Log Decisions

**MUST** log decisions for:
- Technology choices (databases, frameworks, libraries)
- Architectural patterns (microservices, event-driven, layered)
- API design approaches (REST, GraphQL, gRPC)
- Data modeling decisions
- Security architecture choices
- Performance optimization strategies
- Integration approaches
- Deployment strategies

## Knowledge Graph Building

**MUST** proactively link related architectural items using link_conport_items

**SHOULD** use relationship types: "depends_on", "replaces", "implements", "conflicts_with"

## ConPort Tools Usage

**MUST** use server: conport with workspace_id parameter

### Context Management
- get_product_context - Overall project architecture, goals, constraints
- update_product_context - Major architectural changes
- get_active_context - Current planning focus
- update_active_context - Update planning context when switching focus

### Decision & Pattern Management
- log_decision - Record architectural decisions (primary tool)
- get_decisions - Review past architectural decisions
- search_decisions_fts - Search decision history
- log_system_pattern - Document architectural patterns, conventions
- get_system_patterns - Review established patterns

### Knowledge Operations
- semantic_search_conport - Natural language search across all documentation
- link_conport_items - Connect related decisions/patterns/specs
- get_linked_items - Find related architectural items

## Sync Command

When user says "Sync ConPort" or "ConPort Sync":
1. Send [CONPORT_SYNCING] status
2. Review conversation for all architectural decisions made
3. Log missing decisions with full context
4. Link related items in knowledge graph
5. Update active_context to reflect current planning state
6. Resume previous task
