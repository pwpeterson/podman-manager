# File Operations Rules

## File Reading

**read_file** - Read 1-5 files at once (supports PDF/DOCX)
- Parameters: args array with file objects containing path
- **MUST** batch related file reads in single call for efficiency

## File Writing

**write_file** - Create new file or completely overwrite existing
- Parameters: path, content
- **MUST** use only for new files - prefer edit_file for modifications

**edit_file** - Surgical line-based edits with exact text matching
- Parameters: path, edits array (oldText, newText), optional dryRun
- Returns git-style diff
- **MUST** use for targeted changes - most efficient approach

## Directory Operations

**create_directory** - Create directory structure
- Parameters: path (creates nested dirs automatically)

**list_directory** - List directory contents
- Parameters: path, optional recursive flag

## Search Operations

**search_files** - Regex search across files
- Parameters: path, regex, optional file_pattern (glob)
- Returns context-rich results with surrounding lines
- **MUST** use to find patterns across codebase

## Command Execution

**MUST** use execute_command MCP server, NOT filesystem server

**execute_command** - Run bash, python, or supabase commands
- Parameters: command (string), command_type ('bash'|'python'|'supabase')
- Returns: success, returncode, stdout, stderr, execution_time, working_directory
- **IMPORTANT**: Always use the execute_command server for command execution, never filesystem server
