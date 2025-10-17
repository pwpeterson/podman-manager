# Response Format Rules

## Code Linking

**MUST** link code/files as: [`syntax`](path:line) or [filename](path)

## Communication Style

**MUST** be direct and technical - skip conversational phrases like "Great!" or "Certainly!"

**MUST** provide honest feedback and critical evaluation rather than automatic agreement

**MUST** prefer code/diffs over prose explanations

## Task Completion

**MUST** end tasks with MCP attempt-completion service, not with questions

**MUST** use MCP server: attempt-completion with tool: attempt_completion

**MUST** only use attempt_completion after confirming all tool uses succeeded

## File Reading

**MUST** read ≤5 files per call when using read_file

**MUST** batch related file reads in single read_file call for efficiency
