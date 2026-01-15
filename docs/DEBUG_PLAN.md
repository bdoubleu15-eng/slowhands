# SlowHands Launcher Debug Plan

## Problem Statement
The launcher spawns a new terminal window (WSL), but the window opens and immediately closes, even after updates to keep it open and avoid WSL's `--cd` flag.

## Current Implementation Analysis

### Launcher Flow (WSL path)
1. Detects WSL via `/proc/version` check
2. Uses `cmd.exe /c start "" wsl.exe --exec bash -lc "..."` 
3. Sets `SLOWHANDS_KEEP_OPEN=1` environment variable
4. Runs `python app/run_ui.py` with filtered args
5. On exit, should prompt "Press Enter to close" if `SLOWHANDS_KEEP_OPEN` is set

### Potential Failure Points

#### 1. **Command Execution Failure (Most Likely)**
   - `bash -lc` might be failing before reaching the Python script
   - `set -e` in the launcher causes immediate exit on any error
   - Path issues: `$SCRIPT_DIR` might not resolve correctly in nested WSL context
   - Python/venv not found in the new shell context

#### 2. **Environment Variable Not Propagating**
   - `SLOWHANDS_KEEP_OPEN=1` might not be set when Python exits
   - Environment might be reset in the new shell

#### 3. **Terminal Emulator Behavior**
   - `cmd.exe /c start` might not wait for the process
   - Window closes before error messages can be seen

#### 4. **Python Script Immediate Exit**
   - `app/run_ui.py` might be crashing immediately
   - Import errors, missing dependencies
   - Textual UI might fail to initialize

## Debug Plan

### Phase 1: Add Logging & Error Capture

#### 1.1 Create Debug Wrapper Script
Create `debug_launcher.sh` that:
- Logs all steps to a file (`/tmp/slowhands_debug.log`)
- Captures stderr/stdout
- Tests each component individually
- Shows environment variables

#### 1.2 Modify Launcher for Debug Mode
Add `--debug` flag that:
- Disables `set -e` temporarily
- Adds `set -x` for command tracing
- Logs environment variables
- Tests path resolution
- Verifies Python/venv availability

### Phase 2: Test Components Individually

#### 2.1 Test Path Resolution
```bash
# In spawned terminal, verify:
echo "SCRIPT_DIR: $SCRIPT_DIR"
cd "$SCRIPT_DIR" && pwd
ls -la "$SCRIPT_DIR/slowhands"
```

#### 2.2 Test Python Availability
```bash
# Check Python in spawned context:
which python
python --version
python -c "import sys; print(sys.executable)"
```

#### 2.3 Test Venv Activation
```bash
# Test venv if it exists:
if [ -d "venv" ]; then
    source venv/bin/activate
    which python
    python -c "import sys; print(sys.executable)"
fi
```

#### 2.4 Test run_ui.py Directly
```bash
# Try running Python script directly:
python app/run_ui.py --help
python app/run_ui.py 2>&1 | head -20
```

### Phase 3: Fix Terminal Window Behavior

#### 3.1 Test WSL Command Manually
Run the exact command that launcher uses:
```bash
wsl.exe --exec bash -lc "cd '/home/dub/projects/slowhands/app' && SLOWHANDS_NEW_WINDOW=1 SLOWHANDS_KEEP_OPEN=1 '/home/dub/projects/slowhands/app/slowhands' --no-new-window"
```

#### 3.2 Test with Explicit Keep-Alive
Add explicit keep-alive before Python runs:
```bash
# Add trap to catch exits
trap 'echo "Script exited with code $?"; read -p "Press Enter..." _' EXIT
```

#### 3.3 Test Different Terminal Invocation Methods
Try alternatives:
- `wsl.exe -e bash -c "..."` (without --exec)
- `wsl.exe -d <distro> -e bash -c "..."`
- Use `wt.exe` (Windows Terminal) instead of `cmd.exe`

### Phase 4: Add Error Handling

#### 4.1 Wrap Python Execution
```bash
# Capture Python exit code and errors
python app/run_ui.py "${@//--no-new-window/}" 2>&1 | tee /tmp/slowhands_python.log
exit_code=$?
echo "Python exited with code: $exit_code" >> /tmp/slowhands_python.log
```

#### 4.2 Add Pre-flight Checks
Before running Python:
- Verify script exists
- Verify Python is available
- Verify venv (if exists) is valid
- Check file permissions

### Phase 5: Improve Keep-Open Logic

#### 5.1 Always Keep Window Open on Error
```bash
# Modify exit handling:
if [ -n "${SLOWHANDS_KEEP_OPEN:-}" ] || [ "$exit_code" -ne 0 ]; then
    echo
    echo "SlowHands exited with code ${exit_code}"
    echo "Check /tmp/slowhands_debug.log for details"
    read -r -p "Press Enter to close this window..." _
fi
```

#### 5.2 Add Error Message Display
Show last N lines of error log before prompt

## Immediate Action Items

### Step 1: Create Debug Version
1. Copy `slowhands` to `slowhands.debug`
2. Add debug logging
3. Disable `set -e` temporarily
4. Add `set -x` for tracing

### Step 2: Test Manually
1. Run debug version manually in WSL
2. Check what fails first
3. Review `/tmp/slowhands_debug.log`

### Step 3: Test Spawned Terminal
1. Use debug version in launcher
2. Capture output before window closes
3. Check if error messages appear

### Step 4: Fix Root Cause
Based on findings:
- Fix path issues
- Fix Python/venv detection
- Fix command quoting
- Fix terminal invocation

## Expected Issues & Solutions

### Issue: Python not found
**Solution**: Use full path or ensure PATH is set correctly

### Issue: Import errors
**Solution**: Verify venv activation, check dependencies

### Issue: Textual UI fails to start
**Solution**: Check terminal capabilities, TTY availability

### Issue: Command quoting breaks
**Solution**: Use array-based argument passing or better quoting

### Issue: Window closes before errors visible
**Solution**: Redirect output to file, add explicit pause before exit

## Success Criteria

1. Terminal window stays open after Python exits
2. Error messages are visible if Python fails
3. Debug log captures all execution steps
4. Launcher works reliably across different WSL configurations
