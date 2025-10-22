# Container File Validation Feature

## Overview

A comprehensive container file validation system has been added to the Podman Manager to prevent installation of problematic `.container` files. This validation runs automatically during the `pm install` process and catches common issues before they cause systemd service loading failures.

## What It Does

The validation system checks for:

### 1. Invalid/Deprecated Parameters
- **`Expose`** → Should use `PublishPort`
- **`Port`/`Ports`** → Should use `PublishPort`
- **`Env`** → Should use `Environment`
- **`EnvFile`** → Should use `EnvironmentFile`
- **`Volumes`** → Should use `Volume`
- **`Networks`** → Should use `Network`

### 2. Section-Specific Parameter Issues
- **`Restart` in `[Container]` section** → Should be in `[Service]` section
- **`RestartPolicy` in `[Container]` section** → Should be in `[Service]` section

### 3. Missing Environment Variables
- Detects unresolved environment variable references like `${POSTGRES_DB}`
- Distinguishes between variables with default values (`${VAR:-default}`) and those without
- Reports missing variables as errors, variables with defaults as warnings

### 4. Configuration Issues
- Missing required `[Container]` section
- Missing required `Image` parameter
- Invalid port format in `PublishPort`
- Non-existent `EnvironmentFile` references

## How It Works

### Integration with `pm install`

The validation is automatically triggered during the `pm install` process:

1. **Before File Copying**: Validation runs before any `.container` files are copied to systemd
2. **Error Handling**: If critical errors are found, installation is aborted
3. **Warning Handling**: Warnings are displayed but don't block installation
4. **Clear Feedback**: Detailed error messages explain exactly what needs to be fixed

### Example Output

```
Validating 1 container file(s)...
✗ local-ai-postgres.container: 3 error(s)
  • Invalid parameter 'Expose' in [Container] section. Use 'PublishPort' instead.
  • Invalid parameter 'Restart' in [Container] section. Use 'RestartPolicy' in [Service] section instead.
  • Environment variable 'POSTGRES_DB' is not set and has no default value
⚠ local-ai-postgres.container: 1 warning(s)
  • Environment variable 'POSTGRES_VERSION' not set, will use default value

Validation failed: 3 error(s) found across 1 file(s)
Installation aborted due to validation errors.
Fix the errors above and try again.
```

## Files Added/Modified

### New Files
- **`container_validator.py`** - Core validation logic
- **`test_container_validation.py`** - Comprehensive test suite
- **`CONTAINER_VALIDATION.md`** - This documentation

### Modified Files
- **`installer.py`** - Integrated validation into install workflow
  - Added `ContainerValidator` import
  - Added `_validate_container_files()` method
  - Integrated validation call before file copying

## Testing

The validation system includes comprehensive tests that verify:

- ✅ Valid container files pass validation
- ✅ Files with `Expose` parameter are rejected
- ✅ Files with `Restart` in `[Container]` section are rejected
- ✅ Missing environment variables are detected
- ✅ Invalid parameter names are caught
- ✅ Missing required sections/parameters are identified

Run tests with:
```bash
python test_container_validation.py
```

## Benefits

### 1. Prevents Service Loading Failures
- Catches issues like the `local-ai-postgres` service loading problem
- Prevents "Unit not loaded" errors caused by invalid `.container` files

### 2. Clear Error Messages
- Specific guidance on how to fix each issue
- Distinguishes between critical errors and warnings

### 3. Early Detection
- Problems are caught before files are copied to systemd
- No need to debug systemd service failures after installation

### 4. Comprehensive Coverage
- Validates against known quadlet/systemd parameters
- Checks environment variable resolution
- Validates common configuration patterns

## Example: Fixed Issues

The validation would have caught the original `local-ai-postgres` issues:

**Before (Problematic)**:
```ini
[Container]
Image=docker.io/postgres:${POSTGRES_VERSION:-latest}
Expose=5432:5432                    # ❌ Invalid parameter
Restart=unless-stopped              # ❌ Invalid in Container section
Environment=POSTGRES_DB=${POSTGRES_DB}  # ❌ Missing env var
```

**After (Fixed)**:
```ini
[Container]
Image=docker.io/postgres:latest
PublishPort=5432:5432              # ✅ Correct parameter
Environment=POSTGRES_DB=mydb       # ✅ Set value

[Service]
Restart=always                     # ✅ Correct section
```

## Future Enhancements

Potential improvements could include:

1. **Custom Rules**: Allow project-specific validation rules
2. **Auto-Fix**: Suggest or automatically apply common fixes
3. **Integration**: Validate during container file editing
4. **Extended Checks**: Network connectivity, volume path validation
5. **Configuration**: Allow disabling specific validation rules

## Conclusion

The container validation feature significantly improves the reliability of the `pm install` process by catching common configuration errors before they cause systemd service failures. This proactive approach saves time and provides clear guidance for fixing issues.
