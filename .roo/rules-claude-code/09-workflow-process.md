# Workflow Process Rules

## 4-Step Workflow Process

### 1. Understand the Request

**MUST** check ConPort context if [CONPORT_ACTIVE]

**SHOULD** review relevant decisions and progress

**MUST** identify which tools will be needed

**MUST** identify tasks suitable for vLLM delegation

**SHOULD** check vLLM health if planning heavy delegation

### 2. Gather Information

**SHOULD** read necessary files

**SHOULD** search codebase for patterns

**SHOULD** check external documentation if needed

**SHOULD** review related ConPort decisions

**SHOULD** use analyze_codebase for project-wide understanding

### 3. Execute Changes

**SHOULD** for simple, isolated tasks: delegate to vLLM tools

**MUST** inform user: "Delegating [task] to local Qwen2.5-Coder..."

**SHOULD** for complex, integrated tasks: implement directly

**MUST** always review and improve delegated output

**SHOULD** for file edits: Use precommit&fix for automated corrections, or delegate simple edits to vLLM

**MUST** make code changes using appropriate tool

**SHOULD** use security_scan_code for security validation

**SHOULD** use vllm-delegator git tools for version control when appropriate

**SHOULD** use precommit&fix for automated code quality fixes

**SHOULD** log significant decisions to ConPort

**MUST** update progress as tasks complete

**SHOULD** verify changes didn't break anything

### 4. Complete Task

**MUST** mark progress DONE in ConPort

**SHOULD** update active_context if switching focus

**SHOULD** mention delegation when used: "Generated with local LLM, reviewed and verified"

**MUST** present results with MCP attempt-completion service

**MUST** provide clear summary of what was accomplished

## Workflow Optimization

**SHOULD** batch related file reads in single read_file call

**MUST** use edit_file for targeted changes instead of write_file

**SHOULD** link related ConPort items to build project knowledge graph

**SHOULD** update active_context when context switching between tasks

**SHOULD** delegate simple, isolated tasks to vLLM for 2-5x speed improvement

**SHOULD** use git tools from vllm-delegator for streamlined version control

**SHOULD** use health_check to verify vLLM availability before heavy delegation
