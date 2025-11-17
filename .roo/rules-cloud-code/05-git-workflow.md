# Git Workflow Rules

## Git Operations (via git-safe)

**MUST** always use MCP tool interface, never direct git commands

## Available Git Tools

- **git_status** - Check repository status
- **git_log** - Show commit history
- **git_diff** - Show changes (staged or unstaged)
- **git_add** - Stage files for commit
- **git_commit** - Commit with message

## Auto-stage Rule

**MUST** always stage all files (modified + untracked) before commit

**MUST NOT** prompt user about staging choices

## Enhanced Git Operations Best Practices

**MUST** use git_smart_commit for automatic diff analysis and intelligent commit message generation

**MUST** always check git_status before staging or committing

**MUST** review git_diff output to understand changes

**SHOULD** use generate_git_commit_message for manual conventional commits

**MUST** parse git_status JSON output for structured file information

**NOTE**: Auto-push is enabled by default (can be disabled with auto_push: false)

## vLLM Git Tools

**SHOULD** use git tools from vllm-delegator for streamlined version control when appropriate:

- **git_smart_commit** - Analyze changes and auto-generate commit messages with auto-commit/push
- **generate_git_commit_message** - Conventional commit messages (feat, fix, docs, etc.)
- **generate_gitignore** - Language/framework-specific .gitignore files
- **generate_github_workflow** - CI/CD workflow files
- **generate_pr_description** - Comprehensive PR descriptions with context
