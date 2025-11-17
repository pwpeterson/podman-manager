# MCP Servers Reference

## Core MCP Servers

### vllm-delegator
**Local Qwen2.5-Coder-32B-Instruct-AWQ for task delegation (40 tools)**

#### System Health & Monitoring (1 tool)
- health_check - Check vLLM connectivity, disk space, metrics, and configuration status

#### Code Generation & Manipulation (11 tools)
- generate_simple_code - Basic code generation with optional project context
- complete_code - Fill in function bodies, complete classes
- explain_code - Quick code explanations (brief or detailed)
- generate_docstrings - Documentation in multiple styles (Google, NumPy, Sphinx, JSDoc, Rustdoc)
- generate_tests - Unit tests (pytest, unittest, jest, mocha, vitest, cargo-test)
- refactor_simple_code - Simple refactoring patterns (extract method, rename variables, etc.)
- fix_simple_bugs - Fix syntax errors and simple logic bugs
- convert_code_format - Format/style conversions (camelCase↔snake_case, JSON↔YAML, etc.)
- generate_boilerplate_file - Complete file templates (REST API, models, configs, etc.)
- improve_code_style - Apply style guides (PEP8, Black, Airbnb, Google, Prettier)
- generate_schema - Data models (Pydantic, SQLAlchemy, JSON Schema, GraphQL, TypeScript, Protobuf)

#### Code Quality & Analysis (9 tools)
- generate_code_review - Automated code review with severity filtering and focus areas
- suggest_refactoring_opportunities - Identify refactoring targets with priority ranking
- generate_performance_analysis - Performance bottleneck analysis with optimization suggestions
- security_scan_code - Security vulnerability detection with fix recommendations
- detect_code_smells - Code quality issue identification (duplications, complexity, naming)
- generate_unit_test_fixtures - Test data and mock object generation
- add_type_annotations - Add comprehensive type hints (Python, TypeScript, JavaScript)
- optimize_imports - Clean up imports (remove unused, sort, group, add missing)
- analyze_codebase - Project-wide analysis (structure, quality, patterns, dependencies)

#### Git & GitHub Operations (9 tools)
- git_smart_commit - Analyze changes and auto-generate commit messages with auto-commit/push
- generate_git_commit_message - Conventional commit messages (feat, fix, docs, etc.)
- generate_gitignore - Language/framework-specific .gitignore files
- generate_github_workflow - CI/CD workflow files (ci, cd, test, release, lint, security)
- generate_pr_description - Comprehensive PR descriptions with context
- git_status - Execute git status with parsed output (modified, added, deleted, untracked)
- git_add - Stage files for commit
- git_commit - Commit with message (auto-push enabled by default)
- git_diff - Show changes (staged or unstaged)
- git_log - Show commit history (configurable limit and format)

### conport
**Project memory system (requires workspace_id parameter)**
- Context Management: get_product_context, update_product_context, get_active_context, update_active_context
- Decision Logging: log_decision, get_decisions, search_decisions_fts
- Progress Tracking: log_progress, get_progress, update_progress
- Knowledge Graph: semantic_search_conport, link_conport_items, get_linked_items

### filesystem
**Extended file operations**
- File ops: read_file, write_file, edit_file, create_directory, list_directory
- Search: search_files, get_file_info
- Advanced: read_multiple_files, directory_tree, move_file

### git-safe
**Safe git operations**
- git_status, git_log, git_diff, git_add, git_commit

## External Integration Servers

### github
**GitHub integration**
- Issues: create_issue, get_issue, list_issues
- PRs: create_pull_request, get_pull_request, list_pull_requests
- Files: get_file_contents, create_or_update_file

### crawl4ai-rag
**Web crawling and RAG**
- Crawling: crawl_single_page, smart_crawl_url
- Query: perform_rag_query, search_code_examples
- Analysis: check_ai_script_hallucinations

### brave-search
**Web search**
- brave_web_search (general queries)
- brave_local_search (local businesses/places)

### context7
**Library documentation**
- resolve-library-id (find library ID from name)
- get-library-docs (fetch current docs for library)

### sqlite
**Database operations**
- read_query, write_query, create_table, list_tables, describe_table

## Usage Rules

**MUST** specify correct server_name when making tool calls

**MUST** use filesystem server for file operations

**MUST** use execute_command server for command execution

**SHOULD** use vllm-delegator for appropriate delegation tasks

**SHOULD** use conport for project memory when [CONPORT_ACTIVE]
