#!/usr/bin/env python3
"""Test script for interactive AI analysis functionality"""

import sys

sys.path.append(".")

from ai_analyzer import ai_analyzer
from config import console


def test_interactive_analysis():
    """Test the interactive AI analysis functionality"""
    console.print("[bold cyan]Testing Interactive AI Analysis[/bold cyan]")
    console.print("This will simulate the interactive analysis workflow.\n")

    # Mock initial analysis result
    mock_result = """### Root Cause Analysis
The service is failing due to a **port conflict** on port 8002.

### Recommended Solutions
1. **Check port usage**: `ss -tulpen | grep 8002`
2. **Stop conflicting service**: `systemctl --user stop conflicting-service`
3. **Restart target service**: `systemctl --user restart target-service`

### Prevention
- Use different ports for different services
- Implement port conflict detection in startup scripts"""

    # Display mock analysis
    console.print("[bold green]AI Log Analysis for test-service[/bold green]")
    console.print()
    ai_analyzer._render_markdown_manually(mock_result)

    # Show the analysis menu (which will trigger interactive mode)
    ai_analyzer._show_analysis_menu("logs", "test-service")


if __name__ == "__main__":
    test_interactive_analysis()
