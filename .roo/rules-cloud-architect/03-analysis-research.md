# Analysis & Research Rules

## File Analysis

**read_file** - Read up to 5 files at once for context
- **MUST** use to understand current implementation
- **SHOULD** analyze existing patterns and conventions

**list_files** - Explore directory structure
- **MUST** use to map project organization
- **SHOULD** identify relevant modules

**search_files** - Find patterns across codebase
- **MUST** use to discover existing implementations
- **SHOULD** identify refactoring opportunities
- **SHOULD** understand code conventions

**list_code_definition_names** - Get high-level code structure
- **MUST** use to understand module architecture
- **SHOULD** identify key abstractions
- **SHOULD** map component relationships

## Command Analysis

**execute_command** - Run analysis commands (read-only)
- **SHOULD** check dependencies (e.g., `npm list`, `pip freeze`)
- **SHOULD** analyze metrics (e.g., `cloc`, test coverage)
- **SHOULD** examine configurations
- **MUST NOT** make any changes to the system

## External Research

**crawl4ai-rag** - Study documentation for technologies
- **SHOULD** use smart_crawl_url to fetch documentation sites
- **SHOULD** use perform_rag_query to search crawled documentation
- **SHOULD** use search_code_examples to find implementation examples

**context7** - Get current API documentation
- **MUST** use resolve-library-id to find library by name
- **MUST** use get-library-docs to fetch current API docs
- **CRITICAL** for ensuring recommendations use current APIs

**brave-search** - Research best practices
- **SHOULD** use brave_web_search for technical research, best practices, comparisons
- **SHOULD** use brave_local_search if relevant for location-based features

**github** - Repository research
- **SHOULD** use search_repositories to find similar implementations
- **SHOULD** use get_file_contents to analyze other projects
- **SHOULD** use list_issues to understand common problems

## Research Checklist for Technologies

**MUST** evaluate each technology option on:
- Community size and activity
- Production maturity and case studies
- Documentation quality
- Performance characteristics
- Security track record
- Team learning curve
- Operational complexity
- Total cost of ownership
