# ConPort Memory Integration Rules

## Initialization on First Message

**MUST** follow this sequence:
1. Get workspace_id from ${workspaceFolder}
2. Check for context_portal/context.db via list_directory
3. If database exists:
   - Load context: get_product_context, get_active_context
   - Load recent items: get_decisions(limit:5), get_progress(limit:5)
   - Set status: [CONPORT_ACTIVE]
   - Present options: Continue previous task? Review recent activity? Start new task?
4. If no database:
   - Ask: Initialize ConPort for this project?
   - Set status: [CONPORT_ACTIVE] or [CONPORT_INACTIVE]

## Status Indicator

**MUST** begin every response with [CONPORT_ACTIVE] or [CONPORT_INACTIVE]

## Proactive Logging Strategy

**MUST** log implementation decisions as they're made

**MUST** mark progress DONE immediately after task completion

**SHOULD** link related decisions/patterns to build knowledge graph

**MUST** update active_context when switching focus

**SHOULD** document non-obvious coding patterns

**SHOULD** log successful delegation patterns for future optimization

**SHOULD** log code quality findings from security scans and reviews

## Sync Command

When user says "Sync ConPort" or "ConPort Sync":
1. Send [CONPORT_SYNCING] status
2. Review conversation for new decisions, progress updates, context changes
3. Update ConPort with all identified changes
4. Resume previous task

## ConPort Tools Usage

**MUST** use server: conport with workspace_id parameter for all ConPort operations

### Context Management
- get_product_context - Overall project goals, features, architecture
- update_product_context - Major project changes
- get_active_context - Current session focus, recent changes, open issues
- update_active_context - Current task/focus updates

### Decision & Progress Tracking
- log_decision - Record architectural/implementation decisions
- get_decisions - Retrieve decisions with filters
- log_progress - Log task status (TODO/IN_PROGRESS/DONE)
- get_progress - Retrieve progress entries

### Knowledge Operations
- semantic_search_conport - Natural language search across all data
- link_conport_items - Create relationships between items
- get_linked_items - Find related items
