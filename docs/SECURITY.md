# SlowHands Security Guide

This document describes security features, configuration options, and best practices for running SlowHands safely.

## Security Architecture

SlowHands implements defense-in-depth with multiple security layers:

1. **Workspace Isolation** - File operations restricted to designated directory
2. **Command Filtering** - Dangerous shell commands blocked
3. **Code Sandboxing** - Python execution in isolated subprocess
4. **Path Validation** - Protection against directory traversal attacks
5. **Prompt Injection Protection** - System prompt safeguards
6. **CORS Restrictions** - API access limited to trusted origins
7. **Rate Limiting** - Protection against API abuse

## Configuration Security

### API Keys

API keys are loaded from `config/.env` and should **never** be committed to version control.

```bash
# Good: Use environment file
cp config/.env.example config/.env
chmod 600 config/.env  # Restrict permissions

# Bad: Hardcoding keys in code
# NEVER do this
```

The `.gitignore` file excludes `config/.env` by default.

### CORS Configuration

By default, CORS is restricted to localhost origins:

```env
# Default allowed origins (configured in config.py)
# - http://localhost:*
# - http://127.0.0.1:*
# - https://localhost:*
# - https://127.0.0.1:*
# - file://* (Electron)
# - electron://* (Electron)

# To customize:
ALLOWED_CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

**Warning**: Never set `allow_origins=["*"]` in production.

### Debug Logging

Debug logging is disabled by default for security:

```env
# Enable only for development/debugging
ENABLE_DEBUG_LOGGING=false

# If enabled, logs go to workspace/.debug.log by default
# Or specify custom path:
DEBUG_LOG_PATH=/path/to/debug.log
```

Debug logs may contain sensitive information. Never enable in production.

## Tool Security

### File Operations (`file_ops`)

**Protections:**
- All paths resolved relative to workspace directory
- Absolute paths validated against allowed directories
- Path traversal attacks blocked (`../` sequences)

```python
# These are blocked:
file_ops.execute(action="read", path="../../../etc/passwd")
file_ops.execute(action="read", path="/etc/passwd")

# Only workspace paths allowed:
file_ops.execute(action="read", path="myfile.py")  # OK
```

**Configuration:**
```env
WORKSPACE_PATH=/path/to/safe/workspace
```

### Code Execution (`run_python`)

**Protections:**
- Code runs in isolated subprocess
- 30-second timeout by default
- Stdout/stderr captured
- No access to parent process memory

```env
ALLOW_CODE_EXECUTION=true  # Set to false to disable
```

**Limitations:**
- No network access restrictions (use firewall if needed)
- No filesystem sandboxing beyond Python's capabilities
- Consider containerization for untrusted code

### Terminal Commands (`terminal`)

**Protections:**
- Commands run within workspace directory only
- Dangerous command patterns blocked
- 60-second maximum timeout
- PYTHONPATH cleared for safety

**Blocked Commands:**
```python
DANGEROUS_COMMANDS = [
    "rm -rf", "rm -fr", "rm -r", "rm -f",
    "mkfs", "dd", "format",
    "shutdown", "reboot", "halt",
    "> /dev/sda", "> /dev/sdb",
    "chmod 777", "chown root",
    "wget", "curl", "nc", "netcat", "ssh", "scp"
]
```

**Configuration:**
```env
ALLOW_TERMINAL_EXECUTION=true  # Set to false to disable
```

### Git Operations (`git`)

**Protections:**
- Operations restricted to workspace directory
- 30-second timeout on all commands
- No remote operations (push/pull/fetch blocked by default)

```env
ALLOW_GIT_OPERATIONS=true  # Set to false to disable
```

### Web Search (`web_search`)

**Protections:**
- Requires explicit API key configuration
- No results returned if API key not set
- External requests only to configured search API

```env
ALLOW_WEB_SEARCH=true
WEB_SEARCH_API_KEY=your_serpapi_key  # Required to enable
```

## Prompt Injection Protection

The agent system prompt includes safeguards against prompt injection attacks:

1. **Immutable Core Identity**: Instructions marked as non-overridable
2. **Explicit Boundaries**: Clear separation between system and user content
3. **Override Detection**: Instructions to reject suspicious override attempts
4. **Output Validation**: Tool arguments validated before execution

**What's Protected:**
- User messages attempting to override system behavior
- Malicious content in files being read
- Crafted tool outputs designed to manipulate the agent

**Best Practices:**
- Review agent outputs before executing suggested commands
- Don't give the agent access to untrusted file sources
- Monitor agent behavior for unexpected actions

## Rate Limiting

Protect against API abuse and cost overruns:

```env
# Requests per minute (0 = disabled)
RATE_LIMIT_RPM=60

# Tokens per minute (0 = disabled)
RATE_LIMIT_TPM=90000

# Circuit breaker settings
CIRCUIT_BREAKER_THRESHOLD=5   # Failures before circuit opens
CIRCUIT_BREAKER_TIMEOUT=60.0  # Seconds before retry
```

## Deployment Recommendations

### Development

```env
ENABLE_DEBUG_LOGGING=true
VERBOSE=true
SLOW_MODE=true
```

### Production

```env
ENABLE_DEBUG_LOGGING=false
VERBOSE=false
SLOW_MODE=false
ALLOW_TERMINAL_EXECUTION=false  # Consider disabling
RATE_LIMIT_RPM=30
```

### High Security

```env
ENABLE_DEBUG_LOGGING=false
ALLOW_CODE_EXECUTION=false
ALLOW_GIT_OPERATIONS=false
ALLOW_TERMINAL_EXECUTION=false
ALLOW_WEB_SEARCH=false
MAX_ITERATIONS=5
```

## Incident Response

### If API Key is Exposed

1. Immediately revoke the exposed key in provider dashboard
2. Generate new key
3. Update `config/.env` with new key
4. Review git history for exposure
5. Consider using git-filter-repo to remove from history

### If Suspicious Activity Detected

1. Stop the server: `Ctrl+C` or kill process
2. Review logs in workspace/.debug.log (if enabled)
3. Check workspace directory for unexpected files
4. Review recent agent conversation history
5. Reset agent: POST to `/agent/reset`

## Security Checklist

- [ ] API keys stored in `config/.env`, not in code
- [ ] `config/.env` has restricted permissions (600)
- [ ] `config/.env` is in `.gitignore`
- [ ] Debug logging disabled in production
- [ ] CORS restricted to necessary origins
- [ ] Workspace directory is isolated
- [ ] Rate limiting configured appropriately
- [ ] Unnecessary tools disabled
- [ ] Regular review of agent outputs

## Reporting Security Issues

If you discover a security vulnerability, please report it responsibly:

1. Do not open a public issue
2. Email details to the maintainers
3. Include steps to reproduce
4. Allow reasonable time for fix before disclosure
