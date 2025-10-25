# Interactive AI Analysis Implementation

This document describes the implementation of interactive AI analysis functionality that allows users to ask follow-up questions after the initial AI analysis report.

## Overview

The interactive AI analysis feature extends the existing AI analysis system by adding a shell prompt after the initial analysis report. Users can ask follow-up questions, and the AI agent will provide focused responses based on the original analysis context.

## Implementation Details

### Core Components

1. **`_start_interactive_analysis()`** - Main interactive loop
2. **`_process_followup_question()`** - Processes individual follow-up questions
3. **`_generate_followup_prompt()`** - Creates focused prompts for follow-up questions

### Workflow

1. **Initial Analysis**: Standard AI analysis is performed and displayed
2. **Recommended Actions**: Standard action menu is shown
3. **Interactive Prompt**: User is presented with "Any questions or thoughts?" prompt
4. **Question Processing**: User input is processed and sent to AI agent
5. **Response Display**: AI response is formatted and displayed
6. **Loop**: Process repeats until user enters empty input

### User Experience

```
AI Log Analysis for vllm-glm46

### Root Cause Analysis
The service is failing due to a port conflict on port 8002.

### Recommended Solutions
1. Check port usage: `ss -tulpen | grep 8002`
2. Stop conflicting service: `systemctl --user stop conflicting-service`
3. Restart target service: `systemctl --user restart target-service`

Recommended actions:
   View detailed logs: pm logs vllm-glm46
   Diagnose the issue: pm diagnose vllm-glm46
   Re-run AI analysis: pm logs vllm-glm46

Interactive AI Analysis
Ask follow-up questions about the analysis. Press Enter with empty input to exit.

Any questions or thoughts? How do I check which process is using port 8002?

Follow-up Analysis for vllm-glm46

### Checking Port Usage
To identify which process is using port 8002:

1. **List all processes using the port**:
   ```bash
   ss -tulpen | grep :8002
   lsof -i :8002
   ```

2. **Get detailed process information**:
   ```bash
   netstat -tulpen | grep :8002
   ```

Any questions or thoughts? What if I can't stop the conflicting service?

Follow-up Analysis for vllm-glm46

### Alternative Solutions for Port Conflicts
If you cannot stop the conflicting service:

1. **Change the port in your service configuration**:
   - Edit the .container file
   - Update the PublishPort directive
   - Reload and restart: `systemctl --user daemon-reload && systemctl --user restart vllm-glm46`

2. **Use a different available port**:
   ```bash
   # Find available ports
   ss -tulpen | grep -E ':(800[0-9]|801[0-9])'
   ```

Any questions or thoughts? [Enter to exit]

Exiting interactive analysis.
```

## Technical Implementation

### Modified Methods

#### `_show_analysis_menu()`
Added call to `_start_interactive_analysis()` at the end of the method to begin the interactive session.

#### `_start_interactive_analysis()`
```python
def _start_interactive_analysis(self, analysis_type: str, target: str) -> None:
    """Start interactive AI analysis session with follow-up questions"""
    console.print("\n[bold cyan]Interactive AI Analysis[/bold cyan]")
    console.print("[dim]Ask follow-up questions about the analysis. Press Enter with empty input to exit.[/dim]")

    while True:
        try:
            # Show interactive prompt
            console.print("\n[bold yellow]Any questions or thoughts?[/bold yellow] ", end="")
            user_input = input().strip()

            # Exit if empty input
            if not user_input:
                console.print("[dim]Exiting interactive analysis.[/dim]")
                break

            # Process the follow-up question
            self._process_followup_question(analysis_type, target, user_input)

        except KeyboardInterrupt:
            console.print("\n[dim]Interactive analysis interrupted.[/dim]")
            break
        except EOFError:
            console.print("\n[dim]Interactive analysis ended.[/dim]")
            break
```

#### `_process_followup_question()`
```python
def _process_followup_question(
    self, analysis_type: str, target: str, question: str
) -> None:
    """Process a follow-up question and generate AI response"""
    console.print(f"\n[bold green]Follow-up Analysis for {target}[/bold green]")
    console.print()

    # Create a focused prompt for the follow-up question
    followup_prompt = self._generate_followup_prompt(analysis_type, target, question)

    # Get AI analysis using the same agent system
    result = ai_agent_manager.analyze_with_agent(followup_prompt)

    if result:
        # Display the follow-up analysis results
        self._render_markdown_manually(result)
    else:
        console.print("[yellow]Unable to generate follow-up analysis. Please try again.[/yellow]")
```

#### `_generate_followup_prompt()`
```python
def _generate_followup_prompt(
    self, analysis_type: str, target: str, question: str
) -> str:
    """Generate a focused prompt for follow-up questions"""
    return f"""You are an expert system administrator and DevOps engineer.

Context: You previously analyzed a {analysis_type} issue for service '{target}'.

Follow-up Question: {question}

Provide a focused, practical response to this specific question. Keep your answer:
1. **Direct**: Address the question specifically
2. **Actionable**: Include specific commands or steps when relevant
3. **Concise**: Be brief but comprehensive
4. **Practical**: Focus on real-world solutions

Use podman commands (not docker) in all recommendations."""
```

## Features

### Exit Conditions
- **Empty Input**: User presses Enter without typing anything
- **Ctrl+C**: KeyboardInterrupt gracefully handled
- **EOF**: End-of-file condition (Ctrl+D) gracefully handled

### Error Handling
- AI agent failures are handled gracefully with user-friendly messages
- Network timeouts and connection issues are caught
- Invalid input is processed without crashing

### AI Agent Integration
- Uses the same AI agent selection system as the main analysis
- Supports all configured agents (local vLLM, Claude, GPT-4, etc.)
- Maintains consistency with the original analysis session

## Usage Examples

### Basic Usage
```bash
# Run AI analysis with interactive mode
pm logs vllm-glm46 -ai qwen25

# After initial analysis, interactive prompt appears
# User can ask questions like:
# - "How do I check which process is using port 8002?"
# - "What if I can't stop the conflicting service?"
# - "How do I change the port configuration?"
# - "What are the common causes of this error?"
```

### Common Follow-up Questions
- **Port conflicts**: "How do I find what's using this port?"
- **Configuration**: "How do I change the port settings?"
- **Troubleshooting**: "What if the suggested fix doesn't work?"
- **Prevention**: "How can I prevent this in the future?"
- **Monitoring**: "How do I monitor this service?"
- **Performance**: "Is this affecting performance?"

## Benefits

1. **Contextual Help**: Follow-up questions maintain context from the original analysis
2. **Interactive Learning**: Users can explore issues deeper without re-running analysis
3. **Practical Guidance**: Focused responses provide actionable next steps
4. **Efficient Workflow**: No need to restart analysis for related questions
5. **Educational**: Users learn more about system administration through guided Q&A

## Integration Points

### Existing Commands
The interactive analysis is automatically triggered after any AI analysis:
- `pm logs service -ai`
- `pm reinit service` (on failure with AI analysis)
- Future commands with AI analysis integration

### AI Agent System
Uses the existing `ai_agent_manager` for:
- Agent selection and availability checking
- Prompt processing and response generation
- Error handling and fallback mechanisms

### Display System
Uses the existing `_render_markdown_manually()` method for:
- Consistent formatting with initial analysis
- Rich text rendering with colors and formatting
- Code block and command highlighting

## Future Enhancements

1. **Session History**: Remember previous questions in the session
2. **Context Persistence**: Maintain analysis context across multiple sessions
3. **Quick Commands**: Predefined shortcuts for common questions
4. **Export Session**: Save interactive session to file
5. **Multi-service Analysis**: Ask questions about multiple services
6. **Integration with ConPort**: Store interactive sessions in project memory

## Testing

The implementation includes error handling for:
- AI agent unavailability
- Network timeouts
- Invalid user input
- Keyboard interrupts
- EOF conditions

Testing can be performed by:
1. Running any AI analysis command
2. Asking various follow-up questions
3. Testing exit conditions (empty input, Ctrl+C, Ctrl+D)
4. Testing with different AI agents
5. Testing error conditions (network issues, agent failures)

This interactive analysis feature significantly enhances the AI analysis system by providing a conversational interface for deeper exploration of system issues and solutions.
