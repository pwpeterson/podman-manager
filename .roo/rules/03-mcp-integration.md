# MCP Integration Standards

These rules govern how Roo interacts with MCP (Model Context Protocol) servers across all modes.

## Server Usage Rules

**MUST** always specify the correct server_name when making MCP tool calls

**MUST** use exact server names as documented:
- filesystem
- execute_command
- git-safe
- conport
- vllm-delegator
- github
- crawl4ai-rag
- brave-search
- context7
- sqlite
- puppeteer
- sequentialthinking

## Tool Call Format

**MUST** use proper MCP tool call format with XML structure

**MUST** include server_name, tool_name, and arguments in JSON format

**MUST** validate JSON arguments before making calls

## Error Handling

**MUST** handle MCP server errors gracefully

**MUST** provide clear error messages to users when MCP calls fail

**MUST** suggest alternative approaches when MCP servers are unavailable

**MUST NOT** retry failed MCP calls more than twice without user confirmation

## Server-Specific Rules

### filesystem server
**MUST** use for all file operations (read_file, write_file, edit_file, etc.)
**MUST** respect file system permissions and workspace boundaries
**MUST** validate file paths are within workspace

### execute_command server
**MUST** use for all command execution, never filesystem server
**MUST** specify command_type (bash, python, supabase)
**MUST** handle command failures appropriately

### conport server
**MUST** include workspace_id parameter for all operations
**MUST** log significant decisions and progress updates
**MUST** link related items in knowledge graph

### vllm-delegator server
**MUST** check health_check before heavy delegation
**MUST** review all delegated output before presenting to user
**MUST** inform user when delegating tasks

### git-safe server
**MUST** use for all git operations, never direct git commands
**MUST** follow auto-staging rules in code mode
**MUST** use for analysis only in architect mode

## Performance Considerations

**SHOULD** batch related operations when possible

**SHOULD** use appropriate tools for the task (don't use heavy tools for simple operations)

**SHOULD** consider tool response times when planning workflows

## Security Considerations

**MUST** never pass sensitive data through MCP tool arguments

**MUST** validate all user inputs before passing to MCP tools

**MUST** respect tool-specific security constraints

**NOTE**: Always consult mode-specific rules for additional MCP integration requirements.
