# MCP Servers Reference

## Core Architecture Servers

### conport
**Project memory and knowledge base (requires workspace_id parameter)**

#### Context Management
- get_product_context - Overall project architecture, goals, constraints
- update_product_context - Major architectural changes
- get_active_context - Current planning focus
- update_active_context - Update planning context when switching focus

#### Decision Logging (Primary Tool)
- log_decision - Record architectural decisions (MUST use for every decision)
- get_decisions - Review past architectural decisions
- search_decisions_fts - Search decision history
- delete_decision_by_id - Remove obsolete decisions

#### Pattern Documentation
- log_system_pattern - Document architectural patterns, conventions
- get_system_patterns - Review established patterns
- delete_system_pattern_by_id - Remove outdated patterns

#### Knowledge Graph
- semantic_search_conport - Natural language search across all documentation
- link_conport_items - Connect related decisions/patterns/specs
- get_linked_items - Find related architectural items

### filesystem
**Extended file operations for analysis**
- read_text_file - Read up to 5 files for context
- list_directory - Explore directory structure
- search_files - Find patterns across codebase
- list_code_definition_names - Get high-level code structure
- directory_tree - Map project organization

### mcp-git-safe
**Git operations (read-only analysis)**
- git_status - Check repository status
- git_log - Analyze commit history
- git_diff - Review changes
- **MUST NOT** use for commits (analysis only)

## External Research Servers

### crawl4ai-rag
**External documentation research**
- smart_crawl_url - Fetch documentation sites
- get_available_sources - List crawled sources
- perform_rag_query - Search crawled documentation
- search_code_examples - Find implementation examples
- **CRITICAL** for studying technology documentation

### context7
**Up-to-date library documentation**
- resolve-library-id - Find library by name
- get-library-docs - Fetch current API docs
- **CRITICAL** for ensuring recommendations use current APIs

### brave-search
**Web research**
- brave_web_search - Technical research, best practices, comparisons
- brave_local_search - Location-based features (if relevant)

### github
**Repository research**
- search_repositories - Find similar implementations
- get_file_contents - Analyze other projects
- list_issues - Understand common problems

## Specialized Analysis Servers

### puppeteer
**UI/UX research**
- puppeteer_navigate - Explore existing applications
- puppeteer_screenshot - Capture UI patterns
- puppeteer_evaluate - Analyze frontend implementations

### sqlite
**Database analysis**
- read_query - Analyze existing schemas
- list_tables - Understand data structure
- describe_table - Review table definitions

### github.com/zcaceres/fetch-mcp
**Documentation fetching**
- fetch_markdown - Retrieve technical documentation
- fetch_html - Get web-based specs
- fetch_txt - Fetch plain text documents
- **USE** for RFCs, specifications, technical docs

### sequentialthinking
**Complex problem solving**
- sequentialthinking - Multi-step architectural analysis
- **USE** for breaking down complex design problems
- **USE** for exploring alternatives systematically

## Planning & Communication Tools

### Built-in Tools
- **update_todo_list** - Create actionable implementation plans
- **ask_followup_question** - Request clarification with 2-4 suggested responses
- **attempt_completion** - Present final architecture/plan
- **switch_mode** - Handoff to Code mode for implementation

## Server Usage Rules

**MUST** use conport for all architectural decision logging

**MUST** use filesystem for code analysis (read-only)

**MUST** use external research servers before making technology recommendations

**SHOULD** use crawl4ai-rag and context7 to ensure current information

**MUST NOT** use git operations for commits (analysis only)

**SHOULD** use sequentialthinking for complex architectural problems
