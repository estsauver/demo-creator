# Demo Creator - World's Best Demo Creation Plugin

## Vision

Demo Creator makes it trivially easy for any developer using Claude Code to create **professional, polished demo videos** of anything they've built. Whether it's a CLI tool, a web app, or both working together, Demo Creator handles the entire pipeline from script generation to final video with AI presenter.

The end goal: **Loom-quality demos generated entirely by AI**, complete with an AI presenter avatar that makes it look like you recorded it yourself.

---

## Onboarding: `/demo:init`

Before creating demos, users run `/demo:init` to configure their project. This flow auto-detects what it can, then guides users through remaining setup with smart defaults.

### Init Flow Overview

```
/demo:init
    │
    ▼
┌─────────────────────────────────────┐
│  Phase 1: Auto-Detection            │
│  - Scan package.json/pyproject.toml │
│  - Detect tech stack (React, etc.)  │
│  - Find running dev server ports    │
│  - Check for existing .demo/ config │
│  - Detect auth patterns (login page)│
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Phase 2: Guided Interview          │
│  - Confirm/override detected values │
│  - Ask about auth strategy          │
│  - Configure test data setup        │
│  - Set recording preferences        │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Phase 3: Credential Setup          │
│  - Check ~/.claude/demo-creds.yaml  │
│  - Prompt for missing API keys      │
│  - Validate credentials work        │
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Phase 4: Validation                │
│  - Can we reach the app URL?        │
│  - Does auth work?                  │
│  - Can we take a screenshot?        │
│  - Are API keys valid?              │
└─────────────────┬───────────────────┘
                  │
                  ▼
        .demo/config.yaml created
        Ready to run /demo
```

### Configuration Files

#### Project Config: `.demo/config.yaml`

```yaml
# .demo/config.yaml - Project-specific demo configuration
version: 1

project:
  name: "my-web-app"
  tech_stack: "nextjs"  # auto-detected

app:
  base_url: "http://localhost:3000"
  health_check: "/api/health"  # optional endpoint to verify app is running

auth:
  strategy: "cookie"  # none | cookie | token | oauth
  login_url: "/login"
  test_user:
    email: "demo@example.com"
    password_env: "DEMO_USER_PASSWORD"  # reference to env var
  # Or for token auth:
  # token_env: "DEMO_AUTH_TOKEN"

test_data:
  setup:
    - "npm run db:seed:demo"
    # Or kubectl commands, API calls, etc.
  teardown:
    - "npm run db:cleanup:demo"
  # Optional: fixture files
  fixtures:
    - "fixtures/demo-drugs.json"
    - "fixtures/demo-users.json"

recording:
  mode: "local"  # local | kubernetes
  viewport:
    width: 1920
    height: 1080
  # Kubernetes settings (if mode: kubernetes)
  kubernetes:
    namespace: "infra"
    helm_chart: "screenenv-job"

voice:
  provider: "elevenlabs"
  voice_id: "${ELEVENLABS_VOICE_ID}"  # from global creds
  # Or override per-project:
  # voice_id: "custom-voice-id"

avatar:
  enabled: false  # Enable when HeyGen is set up
  style: "picture-in-picture"
  position: "bottom-right"

output:
  upload_to: "gcs"  # gcs | s3 | local
  bucket: "${GCS_BUCKET_NAME}"
  make_public: true

integrations:
  linear:
    auto_post: true  # Post demo link to Linear issue
  slack:
    webhook_url: "${SLACK_WEBHOOK_URL}"
    channel: "#demos"
```

#### Global Credentials: `~/.claude/demo-credentials.yaml`

```yaml
# ~/.claude/demo-credentials.yaml - Global credentials (not committed)
version: 1

elevenlabs:
  api_key: "sk_..."
  default_voice_id: "ErXwobaYiN019PkySvjV"

heygen:
  api_key: "..."
  default_avatar_id: "..."

gcs:
  credentials_path: "/path/to/gcs-key.json"
  default_bucket: "demo-creator-uploads"

# Optional integrations
slack:
  default_webhook_url: "https://hooks.slack.com/..."

linear:
  api_key: "lin_..."
```

### Auto-Detection Logic

```python
# What /demo:init detects automatically

def detect_project():
    detected = {}

    # 1. Tech stack from package.json
    if Path("package.json").exists():
        pkg = json.loads(Path("package.json").read_text())
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

        if "next" in deps:
            detected["tech_stack"] = "nextjs"
        elif "react" in deps:
            detected["tech_stack"] = "react"
        elif "vue" in deps:
            detected["tech_stack"] = "vue"
        # etc.

    # 2. Python projects
    elif Path("pyproject.toml").exists():
        detected["tech_stack"] = "python"
        # Check for FastAPI, Django, Flask, CLI tools

    # 3. Find running dev servers
    detected["running_ports"] = find_listening_ports([3000, 5000, 8000, 8080])

    # 4. Check for auth patterns
    if detected.get("tech_stack") == "nextjs":
        # Look for next-auth, clerk, auth0 patterns
        detected["auth_provider"] = detect_auth_provider()

    # 5. Look for existing test data scripts
    if Path("package.json").exists():
        scripts = pkg.get("scripts", {})
        if "seed" in scripts or "db:seed" in scripts:
            detected["seed_command"] = find_seed_command(scripts)

    return detected
```

### Guided Interview Questions

After auto-detection, `/demo:init` asks to confirm/override:

```python
# Phase 2: Guided interview with AskUserQuestion

questions = [
    {
        "header": "App URL",
        "question": f"Detected app at {detected['base_url']}. Is this correct?",
        "options": [
            {"label": detected['base_url'], "description": "Use detected URL"},
            {"label": "Different URL", "description": "I'll specify a different URL"},
            {"label": "Not running yet", "description": "I need to start the app first"}
        ]
    },
    {
        "header": "Auth",
        "question": "How does your app handle authentication for demos?",
        "options": [
            {"label": "No auth needed", "description": "Public pages, no login required"},
            {"label": "Test user login", "description": "Log in with a test account at start of demo"},
            {"label": "Pre-authenticated", "description": "I'll provide a session cookie/token"},
            {"label": "Skip auth pages", "description": "Start demos after the login flow"}
        ]
    },
    {
        "header": "Test data",
        "question": f"Found seed command: '{detected.get('seed_command')}'. Use this for demo setup?",
        "options": [
            {"label": "Yes, use it", "description": "Run this before each demo"},
            {"label": "Different command", "description": "I have a specific demo data script"},
            {"label": "No setup needed", "description": "Demo data is already in place"},
            {"label": "Manual setup", "description": "I'll handle test data myself"}
        ]
    },
    {
        "header": "Recording",
        "question": "How should demos be recorded?",
        "options": [
            {"label": "Local (Recommended)", "description": "Run Playwright locally - faster, simpler"},
            {"label": "Kubernetes", "description": "Use K8s Jobs for isolated environment"},
        ]
    }
]
```

### Validation Checks

Before completing init, validate the setup works:

```python
def validate_setup(config):
    results = []

    # 1. Can we reach the app?
    try:
        response = requests.get(config["app"]["base_url"], timeout=5)
        results.append(("App reachable", True, f"Status {response.status_code}"))
    except Exception as e:
        results.append(("App reachable", False, str(e)))

    # 2. Can we take a screenshot?
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(config["app"]["base_url"])
            page.screenshot(path=".demo/validation_screenshot.png")
            browser.close()
        results.append(("Screenshot", True, "Saved to .demo/validation_screenshot.png"))
    except Exception as e:
        results.append(("Screenshot", False, str(e)))

    # 3. Are API keys valid?
    if config.get("voice", {}).get("provider") == "elevenlabs":
        try:
            # Quick API check
            validate_elevenlabs_key()
            results.append(("ElevenLabs API", True, "Key valid"))
        except Exception as e:
            results.append(("ElevenLabs API", False, str(e)))

    return results
```

### Init Command Output

```
$ /demo:init

🔍 Detecting project configuration...

Detected:
  ├─ Tech stack: Next.js 14
  ├─ Running at: http://localhost:3000
  ├─ Auth: next-auth (credentials provider)
  └─ Seed command: npm run db:seed

[Guided interview with AskUserQuestion...]

✅ Configuration saved to .demo/config.yaml

🔐 Checking credentials...
  ├─ ElevenLabs API key: Found in ~/.claude/demo-credentials.yaml ✓
  ├─ GCS credentials: Found ✓
  └─ HeyGen API key: Not configured (avatar disabled)

🧪 Validating setup...
  ├─ App reachable: ✓ (200 OK)
  ├─ Screenshot test: ✓ (saved to .demo/validation_screenshot.png)
  ├─ Auth flow: ✓ (can log in as demo@test.com)
  └─ ElevenLabs API: ✓ (key valid)

🎉 Ready to create demos! Run /demo to get started.

Tips:
  • View your config: cat .demo/config.yaml
  • Re-run init: /demo:init --force
  • Create first demo: /demo "feature walkthrough"
```

### Re-initialization

Users can re-run `/demo:init` to update settings:

```bash
/demo:init              # Interactive, preserves existing values as defaults
/demo:init --force      # Start fresh, ignore existing config
/demo:init --validate   # Just run validation checks
/demo:init --creds      # Only update credentials
```

---

## Current State (MVP)

### What Works Today

| Capability | Status | Notes |
|------------|--------|-------|
| Browser demo recording | ✅ Full | Playwright-based, 1080p, WebM → MP4 |
| AI script generation | ✅ Full | LLM generates Playwright Python scripts |
| AI narration | ✅ Full | LLM writes narration, ElevenLabs TTS |
| Video compositing | ✅ Full | moviepy/ffmpeg merges video + audio |
| Cloud upload | ✅ Full | GCS with public/signed URLs |
| Resume/checkpoint | ✅ Full | manifest.json tracks all state |
| Terminal demos | ❌ None | Not implemented |
| HeyGen presenter | ❌ None | Not implemented |
| Local recording | ❌ None | Requires Kubernetes |
| Hybrid demos | ❌ None | Can't mix terminal + browser |

### Current Pain Points

1. **Reliability** - Recordings fail or need multiple retries
2. **K8s dependency** - No local fallback, requires cluster access
3. **Slow** - ~20-30 min end-to-end for a 2-min demo
4. **Browser only** - No terminal/CLI demo support
5. **Manual selectors** - Agent guesses selectors, often wrong
6. **No preview** - Can't preview narration before audio generation

---

## Target Capabilities

### Demo Types

#### 1. Terminal Demos (NEW)

Record CLI/terminal sessions for:
- Claude Code sessions (meta-demos of using Claude Code itself)
- Command-line tools and scripts
- Backend operations (database queries, API calls)
- DevOps workflows (kubectl, docker, git)

**Recording Approaches:**

| Approach | Use Case | Output |
|----------|----------|--------|
| **Asciinema** | Embeddable terminal replays | `.cast` file + player embed |
| **Video capture** | Full video production | Screen recording of terminal |
| **Hybrid** | Best of both | Asciinema for text, video for final |

**Script Format (Terminal):**

```yaml
# terminal-demo.yaml
type: terminal
shell: zsh
dimensions:
  cols: 120
  rows: 40

scenes:
  - name: "Install the package"
    actions:
      - type: command
        text: "npm install @example/my-cli"
        delay_after: 2000

  - name: "Run the first command"
    actions:
      - type: command
        text: "fib init my-project"
        delay_after: 3000
      - type: wait_for
        pattern: "Project initialized successfully"

  - name: "Show the result"
    actions:
      - type: command
        text: "ls -la my-project"
        delay_after: 1500
```

**Key Features:**
- Realistic typing simulation (variable speed, occasional "mistakes")
- Intelligent command timing (wait for output before continuing)
- Environment isolation (clean shell state)
- Support for interactive commands (prompts, confirmations)

#### 2. Browser Demos (ENHANCED)

**Current:** Playwright Python scripts, Kubernetes-based recording

**Improvements:**
- **Auto-selector discovery** - Inspect live app to find robust selectors
- **Visual diff detection** - Catch UI changes between stages
- **Local recording option** - Run without Kubernetes
- **Smart waiting** - Wait for network idle, animations complete
- **Retry with backoff** - Automatic retry on flaky selectors

**Script Format (Browser - Enhanced):**

```yaml
# browser-demo.yaml
type: browser
base_url: "http://localhost:3000"
viewport:
  width: 1920
  height: 1080

setup:
  - run: "npm run seed-demo-data"

scenes:
  - name: "Navigate to drugs page"
    actions:
      - goto: "/drugs"
      - wait_for_idle: true
      - highlight:
          selector: ".search-input"
          duration: 1500

  - name: "Search for EGFR"
    actions:
      - click: ".search-input"
      - type: "EGFR"
        human_like: true
      - click: "button:has-text('Search')"
      - wait_for: ".results-list"
      - assert_visible: ".drug-card"

teardown:
  - run: "npm run cleanup-demo-data"
```

#### 3. Hybrid Demos (NEW)

Combine terminal and browser in a single demo:
- Show backend command, then resulting UI change
- Split-screen or sequential views
- Synced timing across both

**Script Format (Hybrid):**

```yaml
# hybrid-demo.yaml
type: hybrid
layout: split  # split | sequential | pip (picture-in-picture)

terminal:
  position: left  # for split layout
  width_percent: 40

browser:
  position: right
  base_url: "http://localhost:3000"

scenes:
  - name: "Run migration"
    terminal:
      actions:
        - command: "python manage.py migrate"
        - wait_for: "Migrations applied"
    browser:
      actions:
        - wait: 2000  # Wait for terminal to finish
        - goto: "/admin/migrations"
        - assert_visible: "text=All migrations applied"

  - name: "Create a user via CLI"
    terminal:
      actions:
        - command: "fib user create --name 'Demo User' --email demo@test.com"
        - wait_for: "User created"
    browser:
      actions:
        - click: "button:has-text('Refresh')"
        - wait_for: "text=Demo User"
        - highlight: ".user-row:has-text('Demo User')"
```

### HeyGen Integration (NEW)

Add AI presenter avatar overlays to make demos look like screen recordings with a human presenter.

**Presenter Styles:**

| Style | Description | Use Case |
|-------|-------------|----------|
| **Picture-in-Picture** | Small avatar bubble in corner | Most demos, non-intrusive |
| **Side-by-Side** | Presenter on left, demo on right | Tutorials, explanations |
| **Intro/Outro** | Full presenter for intro, demo plays, presenter for outro | Product launches |
| **Invisible** | No avatar, just voice | Quick demos, documentation |

**Pipeline Addition:**

```
Stage 8: composite-video
  → Stage 8.5: generate-avatar (NEW)
      - Send narration to HeyGen
      - Generate avatar video segments
      - Composite avatar onto demo video
Stage 9: upload-to-gcs
```

**Script Format (Avatar):**

```yaml
# In narration.yaml
avatar:
  enabled: true
  style: picture-in-picture
  position: bottom-right
  size: small  # small | medium | large
  avatar_id: "heygen_avatar_id"  # Or use default

segments:
  - timestamp: 0
    text: "Hey! Let me show you our new drug search feature."
    avatar_visible: true

  - timestamp: 5
    text: "Watch as I filter by modality..."
    avatar_visible: true

  - timestamp: 15
    text: "And that's it! Super easy to find what you need."
    avatar_visible: true
```

**HeyGen API Integration:**

```python
# utils/heygen_client.py
class HeyGenClient:
    def generate_avatar_video(
        self,
        text: str,
        avatar_id: str,
        voice_id: str = None,  # Use HeyGen voice or provide ElevenLabs audio
        background: str = "transparent",
    ) -> bytes:
        """Generate avatar video segment."""

    def composite_avatar(
        self,
        demo_video: Path,
        avatar_video: Path,
        style: str,  # pip, side-by-side, etc.
        position: str,
        size: str,
    ) -> Path:
        """Overlay avatar onto demo video."""
```

---

## Reliability Improvements

### Current Problems

1. **Selector failures** - Agent guesses wrong selectors
2. **Timing issues** - Actions happen before page ready
3. **K8s flakiness** - Jobs fail or timeout
4. **No retry logic** - Single failure = manual restart

### Solutions

#### 1. Smart Selector Discovery

Before generating script, inspect the live application:

```python
# Stage 1.5: Discover selectors (NEW)
def discover_selectors(page):
    """
    Crawl the target pages and catalog available selectors.
    Returns a map of semantic names to robust selectors.
    """
    selectors = {}

    # Find all interactive elements
    buttons = page.query_selector_all("button, [role='button']")
    for btn in buttons:
        text = btn.inner_text()
        test_id = btn.get_attribute("data-testid")
        aria = btn.get_attribute("aria-label")

        # Prefer test-id > aria > text
        if test_id:
            selectors[text] = f"[data-testid='{test_id}']"
        elif aria:
            selectors[text] = f"[aria-label='{aria}']"
        else:
            selectors[text] = f"button:has-text('{text}')"

    return selectors
```

#### 2. Automatic Retry with Exponential Backoff

```python
# Wrap every action in retry logic
@retry(
    max_attempts=3,
    backoff_factor=2,
    exceptions=(TimeoutError, ElementNotFound),
)
def click_element(page, selector):
    page.wait_for_selector(selector, state="visible", timeout=5000)
    page.click(selector)
```

#### 3. Smart Waiting

```python
# Instead of fixed delays, wait for actual conditions
async def smart_wait(page):
    await page.wait_for_load_state("networkidle")
    await page.wait_for_function("""
        () => !document.querySelector('.loading, .spinner, [aria-busy="true"]')
    """)
    await page.wait_for_timeout(300)  # Brief pause for animations
```

#### 4. Visual Validation

Take screenshots after each action and compare:

```python
def validate_action(page, expected_state: str):
    """
    Use LLM to validate the current page state matches expectations.
    """
    screenshot = page.screenshot()

    response = llm.vision(
        image=screenshot,
        prompt=f"Does this page show: {expected_state}? Answer YES or NO with brief explanation."
    )

    if "NO" in response:
        raise ValidationError(f"Page state mismatch: {response}")
```

#### 5. Graceful Degradation

```python
# If Kubernetes fails, fall back to local
def record_demo(script_path: Path, manifest: Manifest):
    try:
        return record_in_kubernetes(script_path, manifest)
    except K8sError as e:
        logger.warning(f"K8s recording failed: {e}, falling back to local")
        return record_locally(script_path, manifest)
```

---

## Performance Improvements

### Current: ~20-30 minutes

### Target: ~5-10 minutes

| Optimization | Savings | Implementation |
|--------------|---------|----------------|
| **Parallel audio generation** | 3-5 min | Generate segments in parallel, not sequential |
| **Cached selectors** | 1-2 min | Reuse selector discovery across runs |
| **Local recording** | 2-3 min | Skip K8s Job overhead |
| **Streaming TTS** | 1-2 min | Start compositing while audio still generating |
| **Skip unchanged stages** | 2-5 min | If outline unchanged, reuse Stage 2 script |

### Caching Strategy

```python
# utils/cache.py
class DemoCache:
    def __init__(self, demo_id: str):
        self.cache_dir = Path(f".demo/{demo_id}/.cache")

    def get_selectors(self, page_url: str) -> Optional[dict]:
        """Return cached selectors if app unchanged."""
        cache_key = self._hash_page(page_url)
        cache_file = self.cache_dir / f"selectors_{cache_key}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text())
        return None

    def cache_audio_segment(self, text_hash: str, audio: bytes):
        """Cache TTS output for reuse."""
        cache_file = self.cache_dir / f"audio_{text_hash}.mp3"
        cache_file.write_bytes(audio)
```

### Parallel Processing

```python
# Stage 7: Parallel audio generation
async def generate_audio_parallel(segments: list[dict]) -> list[Path]:
    """Generate all audio segments in parallel."""
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(generate_segment(seg))
            for seg in segments
        ]
    return [t.result() for t in tasks]
```

---

## UX Improvements

### 1. Audio Preview (Before Generation)

Add a preview stage where user can hear sample audio before committing:

```python
# Stage 6.5: Preview narration (NEW)
def preview_narration(manifest: Manifest):
    """Generate first 15 seconds of audio for user preview."""
    narration = manifest.get_file("narration.json")
    first_segment = narration["segments"][0]

    preview_audio = elevenlabs.generate(
        text=first_segment["text"],
        voice_id=get_voice_id(),
    )

    # Save preview
    preview_path = manifest.get_file_path("preview_audio.mp3")
    preview_path.write_bytes(preview_audio)

    return preview_path
```

### 2. Interactive Narration Editor

Instead of editing raw JSON, provide a structured interface:

```yaml
# Narration editing prompt for Claude
I'll help you edit the narration. Here are the segments:

1. [0:00-0:05] "Welcome to our drug search demo..."
   → Edit text? Adjust timing? Delete?

2. [0:05-0:12] "Watch as I filter by modality..."
   → Edit text? Adjust timing? Delete?

3. [0:12-0:20] "The results update instantly..."
   → Edit text? Adjust timing? Delete?

[A]dd new segment | [P]review audio | [S]ave and continue
```

### 3. Progress Visualization

Real-time progress with time estimates:

```
Demo Creation Progress
======================

[✓] Stage 1: Outline                    (23s)
[✓] Stage 2: Script                     (1m 42s)
[✓] Stage 3: Validate                   (38s)
[◐] Stage 4: Record                     (1m 12s / ~2m)
    ├─ Scene 1: Navigate         ✓
    ├─ Scene 2: Search           ✓
    ├─ Scene 3: Filter           ◐  Recording...
    └─ Scene 4: Details          ○
[ ] Stage 5: Narration                  (~1m)
[ ] Stage 6: Adjust                     (user input)
[ ] Stage 7: Audio                      (~3m)
[ ] Stage 8: Composite                  (~2m)
[ ] Stage 9: Upload                     (~30s)

Estimated remaining: 8m 30s
```

### 4. One-Command Quick Demos

For simple cases, skip the interview:

```bash
# Full auto - no questions asked
/demo --quick "drug search filtering"

# With options
/demo --terminal --duration=60s "CLI installation walkthrough"

# Specific feature demo
/demo --feature=drug-filtering --style=tutorial
```

---

## Architecture

### Plugin Structure (Updated)

```
demo-creator/
├── .claude-plugin/
│   └── plugin.json
│
├── agents/
│   ├── rough-outline.md           # Stage 1: Analyze → outline
│   ├── discover-selectors.md      # Stage 1.5: Crawl app for selectors (NEW)
│   ├── detailed-script.md         # Stage 2: Write script
│   ├── validate-script.md         # Stage 3: Dry-run validation
│   ├── record-demo.md             # Stage 4: Execute + record
│   ├── generate-narration.md      # Stage 5: Write narration
│   ├── preview-narration.md       # Stage 5.5: Audio preview (NEW)
│   ├── adjust-narration.md        # Stage 6: User review
│   ├── generate-audio.md          # Stage 7: TTS
│   ├── generate-avatar.md         # Stage 7.5: HeyGen avatar (NEW)
│   ├── composite-video.md         # Stage 8: Merge all
│   └── upload-to-gcs.md           # Stage 9: Upload
│
├── commands/
│   ├── init.md                    # /demo:init - project setup (NEW)
│   ├── create.md                  # /demo - main orchestrator
│   ├── quick.md                   # /demo:quick - fast mode (NEW)
│   ├── terminal.md                # /demo:terminal - terminal only (NEW)
│   ├── resume.md                  # /demo:resume - continue from checkpoint (NEW)
│   └── validate.md                # /demo:validate - check setup (NEW)
│
├── skills/
│   ├── screenenv.md               # Playwright guidance
│   ├── asciinema.md               # Terminal recording guidance (NEW)
│   └── heygen.md                  # Avatar generation guidance (NEW)
│
├── utils/
│   ├── manifest.py                # Pipeline state
│   ├── cache.py                   # Caching layer (NEW)
│   ├── retry.py                   # Retry logic (NEW)
│   ├── selectors.py               # Selector discovery (NEW)
│   ├── screenenv_job.py           # K8s recording
│   ├── local_recorder.py          # Local recording (NEW)
│   ├── terminal_recorder.py       # Asciinema integration (NEW)
│   ├── elevenlabs_client.py       # TTS
│   ├── heygen_client.py           # Avatar generation (NEW)
│   ├── video_compositor.py        # Video + audio merge
│   └── gcs_client.py              # Cloud upload
│
├── templates/                     # Script templates (NEW)
│   ├── browser/
│   │   ├── crud-demo.yaml
│   │   ├── search-filter.yaml
│   │   └── wizard-flow.yaml
│   ├── terminal/
│   │   ├── installation.yaml
│   │   ├── cli-walkthrough.yaml
│   │   └── devops-workflow.yaml
│   └── hybrid/
│       ├── backend-frontend.yaml
│       └── api-to-ui.yaml
│
├── tests/                         # Test suite (NEW)
│   ├── test_selectors.py
│   ├── test_recording.py
│   ├── test_audio.py
│   └── fixtures/
│
└── config/                        # Config schemas & defaults (NEW)
    ├── project-config.schema.json # JSON schema for .demo/config.yaml
    ├── credentials.schema.json    # JSON schema for credentials
    └── defaults/
        ├── nextjs.yaml            # Default config for Next.js projects
        ├── react.yaml             # Default config for React projects
        └── python-cli.yaml        # Default config for Python CLI tools
```

### Pipeline Flow (Updated)

```
                    User Input
                        │
                        ▼
            ┌───────────────────────┐
            │   Stage 1: Outline    │
            │   - Analyze codebase  │
            │   - Identify feature  │
            │   - Create outline.md │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Stage 1.5: Discover   │ (NEW)
            │   - Crawl live app    │
            │   - Catalog selectors │
            │   - Cache for reuse   │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Stage 2: Script      │
            │   - Use selector map  │
            │   - Generate script   │
            │   - Add timing hints  │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Stage 3: Validate    │
            │   - Dry-run script    │
            │   - Screenshot scenes │
            │   - Auto-fix issues   │ (NEW)
            └───────────┬───────────┘
                        │
        ┌───────────────┴───────────────┐
        │                               │
        ▼                               ▼
┌───────────────┐               ┌───────────────┐
│ Stage 4a:     │               │ Stage 4b:     │
│ Record Browser│               │ Record Term   │ (NEW)
│ (Playwright)  │               │ (Asciinema)   │
└───────┬───────┘               └───────┬───────┘
        │                               │
        └───────────────┬───────────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Stage 5: Narration   │
            │   - Analyze recording │
            │   - Write script      │
            │   - Generate SRT      │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Stage 5.5: Preview    │ (NEW)
            │   - Generate sample   │
            │   - Play for user     │
            │   - Confirm or adjust │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Stage 6: Adjust      │
            │   - User edits text   │
            │   - Adjust timing     │
            │   - Finalize script   │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Stage 7: Audio       │
            │   - Parallel TTS      │ (IMPROVED)
            │   - Cache segments    │
            │   - Concatenate       │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │ Stage 7.5: Avatar     │ (NEW)
            │   - HeyGen API call   │
            │   - Generate avatar   │
            │   - Match timing      │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Stage 8: Composite   │
            │   - Merge video+audio │
            │   - Add avatar overlay│ (NEW)
            │   - Burn subtitles    │
            └───────────┬───────────┘
                        │
                        ▼
            ┌───────────────────────┐
            │  Stage 9: Upload      │
            │   - GCS upload        │
            │   - Generate URLs     │
            │   - Post to Linear    │ (NEW)
            └───────────┬───────────┘
                        │
                        ▼
                   Final Demo URL
```

---

## Context Engineering

Demo creation is context-intensive. Browser automation generates massive context (DOM trees, screenshots, Playwright scripts), and a full 9-stage pipeline can easily exhaust the context window. This section outlines strategies to keep the plugin efficient and reliable.

### Core Principles

1. **Subagents = Context Isolation** - Each stage runs as a separate subagent with its own context window. This prevents DOM dumps from Stage 1.5 from polluting Stage 7's audio generation.

2. **Progressive Disclosure** - Skills load only essential info upfront; detailed references are read on-demand. Keep SKILL.md files under 500 lines.

3. **Right Model for the Job** - Use `haiku` for fast, simple tasks; `sonnet` for complex reasoning. Don't waste Opus tokens on file searching.

4. **Resumable Agents** - Long-running stages can be resumed by ID if interrupted. The manifest tracks all state.

5. **Minimal Context Transfer** - Pass only essential data between stages via manifest.json, not the full conversation history.

### Model Selection by Stage

| Stage | Model | Rationale |
|-------|-------|-----------|
| 1: Outline | haiku | Simple analysis, low complexity |
| 1.5: Discover selectors | haiku | DOM traversal, no reasoning needed |
| 2: Script generation | sonnet | Complex - needs domain knowledge |
| 3: Validation | haiku | Execute script, check results |
| 4: Recording | haiku | Execute script, minimal reasoning |
| 5: Narration | sonnet | Creative writing, tone matters |
| 5.5: Preview | haiku | Just generate sample audio |
| 6: Adjust narration | sonnet | User interaction, editing |
| 7: Audio generation | haiku | API calls, no reasoning |
| 7.5: Avatar | haiku | API calls, no reasoning |
| 8: Compositing | haiku | Execute commands, check results |
| 9: Upload | haiku | API calls, no reasoning |

### Subagent Configuration

Each stage agent should be configured with:

```yaml
---
name: stage-2-script
description: Generate Playwright script from outline and selector map. Use after Stage 1.5 completes.
tools: Read, Write, Bash
model: sonnet
skills: screenenv
---
```

**Key configuration points:**

- **Restricted tools** - Each agent only gets tools it needs (e.g., validation doesn't need Write)
- **Skills loading** - Only load relevant skills (e.g., `screenenv` for browser stages, `asciinema` for terminal)
- **Model selection** - Explicit model choice per stage

### Dealing with Browser Context

Browser automation is the biggest context challenge. Strategies:

#### 1. Selector Discovery → Compact Format

Instead of passing full DOM to script generation:

```python
# BAD: Full DOM in context
dom_dump = page.content()  # 50KB+ of HTML

# GOOD: Compact selector map
selectors = {
    "search_input": "[data-testid='search']",
    "submit_button": "button:has-text('Search')",
    "results_list": ".results-container"
}
```

#### 2. Screenshots → File Paths, Not Base64

```python
# BAD: Screenshot in context
screenshot_b64 = page.screenshot(encoding="base64")  # 500KB+

# GOOD: Save to file, pass path
screenshot_path = f".demo/{demo_id}/screenshots/scene_{i}.png"
page.screenshot(path=screenshot_path)
# Pass: {"screenshot": "screenshots/scene_1.png"}
```

#### 3. Validation Errors → Structured Summary

```python
# BAD: Full error stack in context
error_dump = traceback.format_exc()  # Multi-KB

# GOOD: Structured summary
error = {
    "scene": 3,
    "action": "click",
    "selector": "button.submit",
    "error_type": "ElementNotFound",
    "suggestion": "Try button:has-text('Submit') instead"
}
```

### Manifest as Context Bridge

The manifest.json serves as the inter-stage communication channel:

```json
{
  "demo_id": "ISSUE-123-drug-search",
  "stages": [
    {
      "name": "outline",
      "status": "completed",
      "outputs": {
        "outline_path": "outline.md",
        "setup_commands": ["npm run seed"],
        "teardown_commands": ["npm run cleanup"]
      }
    },
    {
      "name": "selectors",
      "status": "completed",
      "outputs": {
        "selector_map_path": "selectors.json",
        "pages_crawled": 3,
        "selectors_found": 47
      }
    }
  ]
}
```

**Rules:**
- Pass file paths, not file contents
- Pass counts and summaries, not full data
- Each stage reads only what it needs from previous outputs

### Skills: Progressive Disclosure

For the `screenenv` skill:

```
skills/
└── screenenv/
    ├── SKILL.md           # 200 lines - core concepts only
    ├── selectors.md       # Detailed selector patterns
    ├── waiting.md         # Smart waiting strategies
    └── troubleshooting.md # Common error fixes
```

**SKILL.md structure:**

```yaml
---
name: screenenv
description: Playwright browser automation for demo recording. Use when writing or debugging browser demo scripts.
---

## Core Concepts

[Essential 200-line overview]

## Additional Resources

- For selector patterns, see [selectors.md](selectors.md)
- For waiting strategies, see [waiting.md](waiting.md)
- For troubleshooting, see [troubleshooting.md](troubleshooting.md)
```

Claude loads additional files only when the task requires them.

### Resumable Long-Running Stages

For stages that might exceed context (e.g., complex script generation):

```yaml
---
name: stage-2-script
description: Generate Playwright script. RESUMABLE - can continue from checkpoint.
---

## Resumption Protocol

If context is running low:
1. Save current progress to script_draft.py
2. Update manifest with {"partial": true, "lines_written": N}
3. Return agent ID for resumption

When resumed:
1. Read script_draft.py
2. Continue from line N
3. Complete remaining scenes
```

### Context Budget Monitoring

Each stage should monitor context usage:

```python
# utils/context_monitor.py
class ContextMonitor:
    MAX_CONTEXT = 200_000  # tokens (approximate)
    WARNING_THRESHOLD = 0.7

    def check_budget(self, stage_name: str) -> bool:
        """Warn if approaching context limit."""
        usage = self.estimate_usage()
        if usage > self.WARNING_THRESHOLD * self.MAX_CONTEXT:
            logger.warning(f"{stage_name}: Context at {usage/self.MAX_CONTEXT:.0%}")
            return False
        return True
```

### Anti-Patterns to Avoid

| Anti-Pattern | Problem | Solution |
|--------------|---------|----------|
| Passing full DOM between stages | Exhausts context | Use selector maps |
| Inline screenshots | 500KB+ per image | File paths only |
| Full error tracebacks | Wastes tokens | Structured summaries |
| Loading all skills upfront | Unnecessary context | Progressive disclosure |
| Using Opus for simple tasks | Slow and expensive | Match model to complexity |
| Keeping full history | Context pollution | Fresh context per stage |

---

## Implementation Roadmap

### Phase 1: Reliability & Local Recording
**Goal:** Make existing browser demos rock-solid

- [ ] `/demo:init` onboarding flow
  - [ ] Auto-detect tech stack, ports, auth patterns
  - [ ] Guided interview with AskUserQuestion
  - [ ] Credential management (global + project)
  - [ ] Validation checks (app reachable, screenshot test)
- [ ] Auto-selector discovery (Stage 1.5)
- [ ] Automatic retry with backoff
- [ ] Smart waiting (network idle, animations)
- [ ] Visual validation with LLM
- [ ] Local Playwright recording (no K8s)
- [ ] Better error messages with actionable fixes

### Phase 2: Terminal Demos
**Goal:** Add first-class terminal recording support

- [ ] Asciinema integration
- [ ] Terminal script format (YAML)
- [ ] Realistic typing simulation
- [ ] Command output waiting
- [ ] Video export from asciinema

### Phase 3: Performance & UX
**Goal:** Cut time from 20-30 min to <10 min

- [ ] Parallel audio generation
- [ ] Caching layer (selectors, audio)
- [ ] Audio preview before full generation
- [ ] Interactive narration editor
- [ ] Progress visualization
- [ ] Skip unchanged stages

### Phase 4: Hybrid Demos
**Goal:** Combine terminal + browser seamlessly

- [ ] Hybrid script format
- [ ] Split-screen compositing
- [ ] Synced timing across sources
- [ ] Picture-in-picture layout

### Phase 5: HeyGen Integration
**Goal:** Add AI presenter for Loom-quality output

- [ ] HeyGen API client
- [ ] Avatar generation pipeline
- [ ] Avatar overlay compositing
- [ ] Style options (PiP, side-by-side, intro/outro)
- [ ] Voice sync with avatar lip movement

### Phase 6: Polish & Templates
**Goal:** Make it delightful to use

- [ ] Template library (common demo patterns)
- [ ] One-command quick mode
- [ ] Auto-post to Linear/Slack/GitHub
- [ ] A/B variants (teaser + full)
- [ ] Voice cloning for brand consistency

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| End-to-end time | 20-30 min | <10 min |
| First-try success rate | ~60% | >90% |
| Manual intervention needed | Often | Rare |
| Demo types supported | 1 (browser) | 3 (browser, terminal, hybrid) |
| Output quality | Good | Loom-equivalent |

---

## Open Questions

1. **HeyGen pricing** - Need to evaluate cost per avatar-minute
2. **Asciinema vs direct recording** - Which produces better video quality?
3. **Local vs cloud recording** - Should local be default, K8s optional?
4. **Voice cloning** - ElevenLabs voice clone or HeyGen voice?
5. **Auto-posting** - Which integrations are highest priority? (Linear, Slack, GitHub, Notion)

---

## Appendix: Environment Variables

```bash
# Required
ELEVENLABS_API_KEY=sk_...           # ElevenLabs TTS
GCS_BUCKET_NAME=demo-creator-uploads      # Google Cloud Storage bucket

# Optional - Enhanced Features
HEYGEN_API_KEY=...                   # HeyGen avatar generation
HEYGEN_AVATAR_ID=...                 # Default avatar to use
ELEVENLABS_VOICE_ID=...               # Custom ElevenLabs voice
GOOGLE_APPLICATION_CREDENTIALS=...   # GCS service account

# Optional - Kubernetes (if not using local)
KUBECONFIG=...                       # K8s cluster config
SCREENENV_NAMESPACE=infra            # K8s namespace for Jobs

# Optional - Integrations
LINEAR_API_KEY=...                   # Auto-post to Linear
SLACK_WEBHOOK_URL=...                # Auto-post to Slack
GITHUB_TOKEN=...                     # Auto-comment on PRs
```

---

*Last updated: 2025-01-08*
