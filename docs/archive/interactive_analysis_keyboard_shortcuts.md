# Interactive AI Analysis - Keyboard Shortcuts

The Interactive AI Analysis system has been updated to use keyboard shortcuts instead of text commands for a more intuitive user experience. Additionally, the follow-up analysis now displays the resolved service name instead of the raw target name.

## New Keyboard Shortcuts

### Unix/Linux/macOS Systems (with termios support)

- **^enter**: Submit your question for AI analysis
- **^z**: Exit the interactive analysis session
- **Enter**: Create a new line in your question
- **Backspace**: Delete the last character on the current line
- **Ctrl+C**: Interrupt/cancel the session

### Windows Systems (fallback mode)

- **Double Enter**: Submit your question (press Enter twice in a row)
- **Type 'quit', 'exit', or 'q'**: Exit the interactive analysis session
- **Enter**: Create a new line in your question

## How It Works

### Multi-line Input Support

You can type multi-line questions naturally:

```
==> Why is my service failing?
==> I see these errors in the logs:
==> - Connection refused
==> - Timeout after 30 seconds
==> [Press ^enter to submit]
```

### Real-time Character Input (Unix/Linux/macOS)

On systems with termios support, the system captures keystrokes in real-time:
- Characters appear as you type
- Backspace works immediately
- No need to press Enter to see your input
- ^enter submits immediately
- ^z exits immediately

### Fallback Mode (Windows)

On Windows systems without termios:
- Type your question normally
- Press Enter for new lines
- Press Enter twice in a row to submit
- Type 'quit' to exit

## Implementation Details

### Automatic Detection

The system automatically detects the platform capabilities:

```python
def _setup_keyboard_handler(self) -> None:
    """Setup keyboard handling for interactive input"""
    try:
        import termios
        import tty
        import sys
        self._has_termios = True
    except ImportError:
        # Windows or system without termios
        self._has_termios = False
```

### Character Code Mapping

- **^enter**: ASCII code 10 (0x0A)
- **^z**: ASCII code 26 (0x1A)
- **Ctrl+C**: ASCII code 3 (0x03)
- **Enter**: ASCII code 13 (0x0D)
- **Backspace**: ASCII code 127 (0x7F)

### Terminal State Management

The system properly manages terminal state:
1. Saves current terminal settings
2. Switches to raw mode for character-by-character input
3. Restores original settings when done

## User Experience Improvements

### Before (OLD - 'END' commands)
```
==> Why is my service failing?
I see connection errors
END
```

### After (NEW - Keyboard shortcuts)
```
==> Why is my service failing?
==> I see connection errors
==> [Press ^enter to submit, ^z to exit]
```

## Service Name Resolution

The system now displays resolved service names in follow-up analysis headers:

### Before
```
Follow-up Analysis for kong
```

### After
```
Follow-up Analysis for kong-gateway
```

This improvement shows the actual resolved service name (e.g., `kong-gateway.service` becomes `kong-gateway`) instead of the user's input target (e.g., `kong`).

## Error Handling

- **Empty submissions**: Warns user and continues session
- **Keyboard interrupts**: Gracefully exits with message
- **Terminal errors**: Falls back to basic input mode
- **Import errors**: Automatically uses fallback mode

## Compatibility

- ✅ **Linux**: Full keyboard shortcut support
- ✅ **macOS**: Full keyboard shortcut support
- ✅ **Windows**: Fallback mode with double-Enter submit
- ✅ **SSH/Remote**: Works with proper terminal forwarding
- ✅ **Docker/Containers**: Works in interactive containers

## Migration Notes

This change is **backward compatible** in terms of functionality:
- All existing AI analysis features work the same
- Only the input method has changed
- No changes to AI prompts or responses
- No changes to analysis results or formatting

Users will see the new instructions automatically when they enter interactive analysis mode.
