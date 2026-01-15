# SlowHands Launcher Fixes Applied

## Issues Found & Fixed

### 1. **Python Command Not Found** ✅ FIXED
- **Problem**: Script used `python` but system only has `python3`
- **Fix**: Added Python detection that prefers `python3`, falls back to `python`
- **Location**: Lines 50-54

### 2. **Empty Argument String Causing argparse Error** ✅ FIXED
- **Problem**: `"${@//--no-new-window/}"` string replacement left empty string when `--no-new-window` was the only argument, causing `run_ui.py` to fail with "unrecognized arguments: "
- **Fix**: Properly filter arguments using array filtering instead of string replacement
- **Location**: Lines 42-48, 57-61

### 3. **Script Exiting Before Keep-Open Prompt** ✅ FIXED
- **Problem**: `set -e` could cause immediate exit if Python failed, preventing keep-open prompt from showing
- **Fix**: Temporarily disable `set -e` during Python execution, capture exit code, then show prompt even on errors
- **Location**: Lines 57-70

## Changes Made

1. **Argument Filtering**: Changed from string replacement to proper array filtering
2. **Python Detection**: Added `PYTHON_CMD` variable that detects available Python
3. **Error Handling**: Improved exit code capture and keep-open logic
4. **Keep-Open on Errors**: Now shows prompt even when Python exits with error

## Testing

Run these tests to verify:
```bash
# Test 1: No arguments (should work)
SLOWHANDS_NEW_WINDOW=1 SLOWHANDS_KEEP_OPEN=1 ./slowhands --no-new-window

# Test 2: With --help (should work)
SLOWHANDS_NEW_WINDOW=1 SLOWHANDS_KEEP_OPEN=1 ./slowhands --no-new-window --help

# Test 3: With --web (should work)
SLOWHANDS_NEW_WINDOW=1 SLOWHANDS_KEEP_OPEN=1 ./slowhands --no-new-window --web
```

## Next Steps for WSL Testing

To test the actual WSL window spawning:
1. Run `./slowhands` (without `--no-new-window`) from WSL
2. Check if new terminal window opens and stays open
3. If window still closes immediately, check `/tmp/slowhands_debug.log` (if using debug version)
