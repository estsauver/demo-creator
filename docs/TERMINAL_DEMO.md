# Terminal Demo Recorder

YAML-based terminal demo recorder that outputs asciinema `.cast` files.

## Quick Start

```bash
# Record a demo
python3 terminal_demo.py demo.yaml -o demo.cast

# Validate without recording
python3 terminal_demo.py demo.yaml --dry-run

# Record and preview immediately
python3 terminal_demo.py demo.yaml -o demo.cast --preview

# Record with progress bar
python3 terminal_demo.py demo.yaml -o demo.cast --progress

# Export to GIF
python3 terminal_demo.py demo.yaml -o demo.cast --export-gif demo.gif

# Export narration timing as subtitles
python3 terminal_demo.py demo.yaml -o demo.cast --narration-srt narration.srt

# CI validation mode (exits with error if commands fail)
python3 terminal_demo.py demo.yaml --assert-only

# Parallel validation of multiple scripts (CI mode)
python3 terminal_demo.py demos/*.yaml --parallel --workers 8
```

## Security Considerations

**IMPORTANT: This tool executes shell commands from YAML files.**

### Trusted Input Only

Demo scripts execute arbitrary shell commands with `shell=True`. This is by design (demos need to run real commands), but means:

- **Only run demo scripts from trusted sources** (your own repo, reviewed PRs)
- **Never run demo scripts from untrusted users** or external sources
- **Review YAML files before execution**, especially `run` and `foreach` actions
- **Variable interpolation can execute code** if variables come from untrusted input

### Command Injection Risk

The `{{ variable }}` syntax interpolates directly into shell commands. If variables come from untrusted sources, this allows command injection:

```yaml
# DANGEROUS if API_URL comes from user input!
variables:
  API_URL: "http://example.com; rm -rf /"  # Malicious input

steps:
  - action: run
    content: "curl {{ API_URL }}"  # Executes the malicious command!
```

**Mitigations:**
1. Only use hardcoded variables in demo scripts
2. Never accept variables from external sources (user input, env vars from untrusted contexts)
3. Review all `run` actions in demo scripts before execution

### Environment Variables

The `.cast` output file includes environment variables in the header. Avoid recording demos with sensitive env vars, or use `--redact-env` (coming soon).

### Working Directory

The `cwd` setting allows navigating to any directory. In CI environments, consider sandboxing demo execution.

## Philosophy: Show Experience, Not Evidence

**The most important insight for demo creation.**

A demo should show the *experience* of using a feature, not the *evidence* that it was built. The goal is to make viewers think "I want to use this" not "I see that code exists."

### Bad Demo (What NOT to do)
```yaml
# Shows code exists - this is what a PR already shows!
- action: run
  content: "head -60 backend/app/db/models.py"
- action: run
  content: "pytest tests/ -v"
```

### Even Worse: Simulators
```yaml
# NEVER DO THIS - defeats the entire purpose
- action: run
  content: "python3 fake_api_simulator.py"  # NO!
```

**CRITICAL:** Never create simulators or mock scripts. If the feature isn't working, deploy it first.

### Good Demo
```yaml
# Shows the feature WORKING - the experience!
- action: run
  content: "curl -X POST localhost:8000/graphql -d '...'"
- action: run
  content: "curl -N localhost:8000/api/stream"  # Real SSE events!
```

**Rule:** If your demo could be replaced by linking to the PR diff, it's not a demo.

## YAML Schema

### Settings

```yaml
settings:
  title: "My Demo"           # Title in cast metadata
  shell: /bin/bash           # Shell to use (default: $SHELL)
  cwd: backend/              # Working directory for all commands
  cols: 120                  # Terminal width (default: 120)
  rows: 30                   # Terminal height (default: 30)
  typing_speed: 50           # Milliseconds per character (default: 50)
  post_execute_pause: 500    # Pause after command execution (default: 500)

  env:                       # Environment variables
    DEBUG: "1"
    API_KEY: "test-key"

  error_detection:
    mode: smart              # "smart", "strict", or "off"
    patterns:                # Regex patterns that indicate errors
      - "(?i)^error:"
      - "(?i)^fatal:"
    safe_contexts:           # Patterns that indicate false positives
      - "PASSED"
      - "test_error"
    ignore_patterns:         # Always ignore these
      - "deprecation warning"
```

### Variables

```yaml
variables:
  API_URL: "http://localhost:8000"
  PROJECT: "backend"

steps:
  - action: run
    content: "curl {{ API_URL }}/health"
```

Variables support `{{ name }}` interpolation syntax.

### Actions

#### `run` - Execute a command (recommended)

Combines typing and execution in one step. **Use this for most commands.**

```yaml
- action: run
  content: "pytest tests/ -v"
  cwd: backend/              # Optional: override working directory
  typing_speed: 30           # Optional: override typing speed
  expect_error: false        # Optional: don't flag errors
  ignore_error_patterns:     # Optional: step-specific ignores
    - "deprecation"
```

#### `type` + `execute` - Fine-grained control

For cases where you need to show a command without running it, or add delays.

```yaml
- action: type
  content: "dangerous-command --force"

- action: pause
  duration: 2000

# User decides whether to run...
- action: execute
```

#### `pause` - Wait

```yaml
- action: pause
  duration: 2000  # milliseconds
```

#### `section` - Chapter markers

Creates navigation markers in the cast file.

```yaml
- action: section
  name: "Database Setup"
  content: "Setting up the database"  # Optional: displayed in terminal
```

#### `comment` - Visible comments

```yaml
- action: comment
  content: "Now let's test the API"
```

#### `screenshot` - Screenshot markers

For documentation/narration sync points.

```yaml
- action: screenshot
  name: "final-results"
```

#### `cd` - Change directory

```yaml
- action: cd
  content: "backend/"
```

#### `clear` - Clear terminal

```yaml
- action: clear
```

#### `set` - Set a variable

```yaml
- action: set
  name: "RESULT"
  content: "success"
```

#### `foreach` - Loop over items

```yaml
- action: foreach
  items:
    - "tests/unit"
    - "tests/integration"
    - "tests/e2e"
  template:
    - action: run
      content: "pytest {{ item }} -v"
    - action: pause
      duration: 1000
```

### Narration

Add narration hints for audio generation. Timing is auto-calculated:

```yaml
- action: run
  content: "pytest tests/"
  narration:
    before: "Now let's run the tests"    # Appears before command runs
    after: "All tests passed successfully"  # Timed after command completes
```

Export narration as subtitles:
```bash
python3 terminal_demo.py demo.yaml -o demo.cast --narration-srt narration.srt
python3 terminal_demo.py demo.yaml -o demo.cast --narration-vtt narration.vtt
```

### Metadata

Add metadata to track demos and detect changes:

```yaml
metadata:
  name: "API Demo"
  version: "1.0.0"
  description: "Demonstrates the Discussion Panel API"
  author: "demo-creator@example.com"
```

The source file checksum is automatically computed and included in the `.cast` file header. This helps detect when the demo script has changed since the last recording.

## Smart Error Detection

The default `smart` mode avoids false positives from test output.

### How it works

1. Scans output for error patterns (configurable)
2. Checks if line matches any "safe context" patterns
3. Only flags errors outside safe contexts

### Configuration

```yaml
settings:
  error_detection:
    mode: smart  # or "strict" or "off"

    # Patterns that indicate real errors
    patterns:
      - "(?i)^error:"
      - "(?i)traceback"
      - "command not found"

    # Patterns that indicate false positives
    safe_contexts:
      - "PASSED"
      - "test_\\w*error"  # Test names
      - "ErrorHandler"    # Class names

    # Always ignore these
    ignore_patterns:
      - "deprecation warning"
```

### Per-step overrides

```yaml
- action: run
  content: "pytest tests/"
  ignore_error_patterns:
    - "ERROR"  # Pytest test names contain ERROR
```

### Expecting errors

```yaml
- action: run
  content: "invalid-command"
  expect_error: true  # Won't be flagged
```

## CLI Options

| Option | Description |
|--------|-------------|
| `-o, --output FILE` | Output .cast file path |
| `--dry-run` | Validate without recording |
| `--assert-only` | CI mode: exit 1 if errors |
| `--parallel` | Run multiple scripts in parallel |
| `--workers N` | Number of parallel workers (default: 4) |
| `--preview` | Play recording after creation |
| `--progress` | Show progress bar during recording |
| `--export-gif FILE` | Export to GIF (requires agg) |
| `--gif-theme THEME` | GIF theme (default: monokai) |
| `--narration-srt FILE` | Export narration as SRT subtitles |
| `--narration-vtt FILE` | Export narration as WebVTT subtitles |
| `-v, --verbose` | Verbose output |

## Integration

### With asciinema

```bash
# Play recording
asciinema play demo.cast

# Upload to asciinema.org
asciinema upload demo.cast
```

### With agg (GIF export)

```bash
# Install agg
cargo install --git https://github.com/asciinema/agg

# Export
python3 terminal_demo.py demo.yaml -o demo.cast --export-gif demo.gif
```

### CI/CD Integration

```yaml
# .github/workflows/demo.yml
- name: Validate demo scripts (parallel)
  run: |
    python3 plugins/demo-creator/terminal_demo.py demos/*.yaml --parallel --workers 8
```

Or validate sequentially for detailed output:

```yaml
- name: Validate demo scripts
  run: |
    for script in demos/*.yaml; do
      python3 plugins/demo-creator/terminal_demo.py "$script" --assert-only
    done
```

### Parallel Validation

For CI pipelines with many demo scripts, use parallel mode:

```bash
# Validate all YAML files in a directory
python3 terminal_demo.py demos/ --parallel

# Multiple specific files with custom worker count
python3 terminal_demo.py demo1.yaml demo2.yaml demo3.yaml --parallel --workers 8
```

Output shows pass/fail for each script:
```
PARALLEL VALIDATION RESULTS
============================================================

  PASS: demos/api_demo.yaml
  PASS: demos/pytest_demo.yaml
  FAIL: demos/broken_demo.yaml
       Step 3: command not found...

------------------------------------------------------------
TOTAL: 2/3 passed
============================================================
```

## Examples

See `examples/` directory:

- `api_demo.yaml` - Demonstrates API with curl
- `pytest_demo.yaml` - Test suite demo with foreach

## Best Practices

1. **Show, don't tell** - Run commands, don't show code files
2. **User perspective** - What would a user actually do?
3. **Real data** - Use real API calls, not mocks
4. **Keep it short** - Focus on the "aha" moment
5. **Section markers** - Break long demos into chapters
6. **Test with --dry-run** - Validate before slow recording

## Troubleshooting

### False positive errors

Add patterns to `safe_contexts` or `ignore_patterns`:

```yaml
settings:
  error_detection:
    safe_contexts:
      - "my_custom_pattern"
```

### Commands not found

Check `cwd` setting matches your project structure.

### Slow typing

Reduce `typing_speed` (lower = faster):

```yaml
settings:
  typing_speed: 20  # Very fast
```
