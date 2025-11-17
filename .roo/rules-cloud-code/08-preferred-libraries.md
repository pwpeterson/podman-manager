# Preferred Libraries & Standards

## Logging & CLI Standards

### Primary Logging Library
**MUST** use **loguru** as primary logging library for all Python projects

### CLI Enhancement
**MUST** use **rich.console** for rich text and beautiful formatting for CLI output

**MUST** use **rich.logging** as enhanced logging handler with rich formatting

**SHOULD** use rich.console.Console() for interactive CLI elements

**SHOULD** use rich progress bars, tables, and panels for better UX

**MUST** configure loguru with rich handler for consistent styling

## Implementation Pattern

```python
from loguru import logger
from rich.console import Console
from rich.logging import RichHandler

# Configure loguru with rich handler
logger.configure(
    handlers=[
        {
            "sink": RichHandler(console=Console()),
            "format": "{time} | {level} | {message}"
        }
    ]
)

# Use rich console for interactive elements
console = Console()
console.print("[bold green]Success![/bold green]")
```

## Why These Libraries

- **loguru**: Simplified logging with powerful features
- **rich**: Beautiful terminal output with minimal effort
- **rich.logging**: Seamless integration between loguru and rich
- **rich.console**: Interactive CLI elements with styling

## Usage Guidelines

**MUST** use loguru for all logging operations

**MUST** use rich.console for user-facing output

**SHOULD** use rich components (progress bars, tables, panels) for better UX

**MUST** maintain consistent styling across all CLI interactions
