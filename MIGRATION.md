# Podman Manager Migration Guide

## ✅ Your Existing Aliases Will Continue to Work!

The refactoring maintains **100% backward compatibility**. All your existing bash aliases and scripts will continue to work without any changes.

## How It Works

### Compatibility Wrapper
A smart wrapper script `pm` automatically detects your environment:

- **With uv available**: Uses the new refactored modular version (`main.py`)
- **Without uv**: Falls back to the original monolithic script (`podman-manager.py`)

### Available Entry Points

1. **`./pm`** - Smart wrapper (recommended)
2. **`uv run python main.py`** - New refactored version
3. **`./podman-manager.py`** - Original monolithic version
4. **`python3 podman-manager.py`** - Original version (fallback)

## Existing Aliases Compatibility

If you have aliases like:
```bash
alias pm='/path/to/podman-manager.py'
alias podman-manager='/path/to/podman-manager.py'
```

They will continue to work exactly as before. The original `podman-manager.py` file is preserved and fully functional.

## Migration Path (Optional)

If you want to take advantage of the new modular architecture:

### Option 1: Update Existing Aliases
```bash
# In your ~/.bashrc
alias pm='/path/to/podman_manager/pm'  # Uses smart wrapper
```

### Option 2: Add to PATH
```bash
# Add to ~/.bashrc
export PATH="/path/to/podman_manager:$PATH"
# Now you can use 'pm' from anywhere
```

### Option 3: Create Symlink
```bash
sudo ln -s /path/to/podman_manager/pm /usr/local/bin/pm
```

## Benefits of Migration

### Performance
- **Faster startup**: Modular loading only imports what's needed
- **Better caching**: uv provides faster dependency resolution

### Development
- **Easier maintenance**: Code is organized into logical modules
- **Better testing**: Individual components can be tested separately
- **Extensibility**: Easy to add new features without touching core logic

### Architecture
```
Root Directory:
├── config.py          # Logging & Rich console setup
├── manager.py         # Core business logic
├── container_ops.py   # Container operations
├── display.py         # Rich display components
├── main.py           # New modular entry point
├── podman-manager.py # Original monolithic script
└── pm               # Smart compatibility wrapper
```

## No Action Required

**You don't need to change anything!** Your existing setup will continue to work. The migration is completely optional and can be done at your own pace.

## Testing Both Versions

```bash
# Test original version
./podman-manager.py status

# Test new version
uv run python main.py status

# Test smart wrapper
./pm status
```

All three should produce identical output with the same alphabetically sorted project/service tree.

## Troubleshooting

If you encounter any issues:

1. **Original version not working**: Check file permissions with `chmod +x podman-manager.py`
2. **New version not working**: Ensure uv is installed and dependencies are available
3. **Wrapper not working**: Check that `pm` is executable with `chmod +x pm`

## Questions?

The refactoring maintains the exact same functionality while improving code organization. Your workflow remains unchanged unless you choose to migrate.
