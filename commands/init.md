---
name: init
description: Initialize demo-creator for your project. Auto-detects tech stack, running servers, and auth patterns. Guides you through configuration with smart defaults.
---

# Demo Creator Initialization

You are the Demo Creator initialization agent. Your job is to set up demo-creator for this project by:
1. Auto-detecting project configuration
2. Guiding the user through remaining setup
3. Validating the configuration works
4. Creating the `.demo/config.yaml` file

## Workflow

### Phase 1: Auto-Detection

First, analyze the project to detect as much as possible automatically.

```bash
python3 << 'PYTHON'
import json
import os
import socket
import subprocess
from pathlib import Path

detected = {
    "project": {},
    "app": {},
    "auth": {},
    "test_data": {},
    "recording": {},
}

# 1. Detect tech stack from package.json
if Path("package.json").exists():
    with open("package.json") as f:
        pkg = json.load(f)

    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

    if "next" in deps:
        detected["project"]["tech_stack"] = "nextjs"
    elif "react" in deps:
        detected["project"]["tech_stack"] = "react"
    elif "vue" in deps:
        detected["project"]["tech_stack"] = "vue"
    elif "svelte" in deps:
        detected["project"]["tech_stack"] = "svelte"
    elif "angular" in deps or "@angular/core" in deps:
        detected["project"]["tech_stack"] = "angular"
    else:
        detected["project"]["tech_stack"] = "javascript"

    detected["project"]["name"] = pkg.get("name", Path.cwd().name)

    # Check for auth providers
    if "next-auth" in deps:
        detected["auth"]["provider"] = "next-auth"
    elif "@clerk/nextjs" in deps:
        detected["auth"]["provider"] = "clerk"
    elif "@auth0/nextjs-auth0" in deps:
        detected["auth"]["provider"] = "auth0"

    # Check for seed scripts
    scripts = pkg.get("scripts", {})
    for key in ["seed", "db:seed", "seed:demo", "db:seed:demo"]:
        if key in scripts:
            detected["test_data"]["seed_command"] = f"npm run {key}"
            break

# 2. Detect Python projects
elif Path("pyproject.toml").exists():
    detected["project"]["tech_stack"] = "python"
    detected["project"]["name"] = Path.cwd().name

    try:
        import tomllib
        with open("pyproject.toml", "rb") as f:
            pyproject = tomllib.load(f)
        detected["project"]["name"] = pyproject.get("project", {}).get("name", Path.cwd().name)

        deps = pyproject.get("project", {}).get("dependencies", [])
        if any("fastapi" in d for d in deps):
            detected["project"]["tech_stack"] = "fastapi"
        elif any("django" in d for d in deps):
            detected["project"]["tech_stack"] = "django"
        elif any("flask" in d for d in deps):
            detected["project"]["tech_stack"] = "flask"
    except Exception:
        pass

elif Path("requirements.txt").exists():
    detected["project"]["tech_stack"] = "python"
    detected["project"]["name"] = Path.cwd().name

# 3. Check for running dev servers
common_ports = [3000, 3001, 4000, 5000, 5173, 8000, 8080, 8888]
running_ports = []

for port in common_ports:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.1)
    result = sock.connect_ex(('localhost', port))
    sock.close()
    if result == 0:
        running_ports.append(port)

if running_ports:
    detected["app"]["running_ports"] = running_ports
    detected["app"]["base_url"] = f"http://localhost:{running_ports[0]}"

# 4. Detect existing .demo config
if Path(".demo/config.yaml").exists():
    detected["existing_config"] = True

# 5. Check for common auth patterns in code
auth_indicators = []
try:
    # Look for login routes
    result = subprocess.run(
        ["rg", "-l", "login|signin|auth", "--type", "tsx", "--type", "ts", "--type", "jsx", "--type", "js"],
        capture_output=True, text=True, timeout=5
    )
    if result.stdout.strip():
        auth_indicators = result.stdout.strip().split('\n')[:5]
except Exception:
    pass

if auth_indicators:
    detected["auth"]["has_auth_files"] = True
    detected["auth"]["auth_files"] = auth_indicators

# 6. Check for kubectl (K8s) availability
try:
    result = subprocess.run(["kubectl", "version", "--client", "-o", "json"], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        detected["recording"]["k8s_available"] = True
except Exception:
    detected["recording"]["k8s_available"] = False

# 7. Check for Playwright installation
try:
    result = subprocess.run(["playwright", "--version"], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        detected["recording"]["playwright_available"] = True
except Exception:
    detected["recording"]["playwright_available"] = False

print(json.dumps(detected, indent=2))
PYTHON
```

Display the detection results to the user:

```
Detected configuration:
  Project: {name}
  Tech stack: {tech_stack}
  Running at: {base_url or "Not detected"}
  Auth provider: {auth.provider or "Not detected"}
  Seed command: {test_data.seed_command or "Not found"}
  K8s available: {recording.k8s_available}
  Playwright: {recording.playwright_available}
```

### Phase 2: Guided Interview

Use AskUserQuestion to confirm/override detected values and gather missing info:

```python
# Question 1: App URL
questions = []

if detected.get("app", {}).get("base_url"):
    questions.append({
        "question": f"Detected app at {detected['app']['base_url']}. Is this correct?",
        "header": "App URL",
        "multiSelect": False,
        "options": [
            {"label": detected["app"]["base_url"], "description": "Use detected URL (Recommended)"},
            {"label": "Different URL", "description": "I'll specify a different URL"},
            {"label": "Not running", "description": "App isn't running yet"}
        ]
    })
else:
    questions.append({
        "question": "What URL will your app run at for demo recording?",
        "header": "App URL",
        "multiSelect": False,
        "options": [
            {"label": "http://localhost:3000", "description": "Default React/Next.js port"},
            {"label": "http://localhost:5173", "description": "Default Vite port"},
            {"label": "http://localhost:8000", "description": "Default FastAPI/Django port"},
            {"label": "Different URL", "description": "I'll specify a different URL"}
        ]
    })

# Question 2: Auth strategy
questions.append({
    "question": "How does your app handle authentication for demos?",
    "header": "Auth",
    "multiSelect": False,
    "options": [
        {"label": "No auth needed", "description": "Public pages, no login required"},
        {"label": "Test user login", "description": "Log in with a test account at demo start"},
        {"label": "Pre-authenticated", "description": "I'll provide a session cookie/token"},
        {"label": "Skip auth pages", "description": "Start demos after the login flow"}
    ]
})

# Question 3: Recording mode
questions.append({
    "question": "How should demos be recorded?",
    "header": "Recording",
    "multiSelect": False,
    "options": [
        {"label": "Local (Recommended)", "description": "Run Playwright locally - faster, simpler"},
        {"label": "Kubernetes", "description": "Use K8s Jobs for isolated environment"}
    ]
})

AskUserQuestion(questions=questions)
```

### Phase 3: Credential Setup

Check for existing credentials and prompt for missing ones:

```bash
python3 << 'PYTHON'
import os
from pathlib import Path
import yaml

creds_path = Path.home() / ".claude" / "demo-credentials.yaml"
creds = {}

if creds_path.exists():
    with open(creds_path) as f:
        creds = yaml.safe_load(f) or {}

missing = []

# Check ElevenLabs
if not creds.get("elevenlabs", {}).get("api_key") and not os.getenv("ELEVENLABS_API_KEY"):
    missing.append("ElevenLabs API key (for voice narration)")

# Check GCS
if not creds.get("gcs", {}).get("credentials_path") and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    missing.append("GCS credentials (for video upload)")

# Check HeyGen (optional)
has_heygen = creds.get("heygen", {}).get("api_key") or os.getenv("HEYGEN_API_KEY")

print("Credential status:")
if creds.get("elevenlabs", {}).get("api_key") or os.getenv("ELEVENLABS_API_KEY"):
    print("  ElevenLabs API key: Found")
else:
    print("  ElevenLabs API key: Not found")

if creds.get("gcs", {}).get("credentials_path") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    print("  GCS credentials: Found")
else:
    print("  GCS credentials: Not found")

if has_heygen:
    print("  HeyGen API key: Found (avatar enabled)")
else:
    print("  HeyGen API key: Not found (avatar disabled)")

if missing:
    print("\nMissing credentials:")
    for m in missing:
        print(f"  - {m}")
    print("\nAdd credentials to ~/.claude/demo-credentials.yaml or set environment variables.")
PYTHON
```

If credentials are missing, guide user on how to add them:

```markdown
To add credentials, create or edit ~/.claude/demo-credentials.yaml:

```yaml
elevenlabs:
  api_key: "sk_..."
  default_voice_id: "ErXwobaYiN019PkySvjV"

gcs:
  credentials_path: "/path/to/gcs-key.json"
  default_bucket: "your-demos-bucket"

# Optional - for AI presenter avatar
heygen:
  api_key: "..."
```
```

### Phase 4: Validation

Validate the configuration works:

```bash
python3 << 'PYTHON'
import json
import os
import sys
import requests
from pathlib import Path

results = []

# 1. App reachable?
base_url = "{base_url}"  # From user input
try:
    response = requests.get(base_url, timeout=5)
    results.append(("App reachable", True, f"Status {response.status_code}"))
except Exception as e:
    results.append(("App reachable", False, str(e)))

# 2. Playwright installed?
try:
    from playwright.sync_api import sync_playwright
    results.append(("Playwright", True, "Installed"))
except ImportError:
    results.append(("Playwright", False, "Run: pip install playwright && playwright install chromium"))

# 3. Can take screenshot?
if results[-1][1]:  # Playwright installed
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(base_url, timeout=10000)

            # Create .demo directory
            Path(".demo").mkdir(exist_ok=True)
            page.screenshot(path=".demo/validation_screenshot.png")
            browser.close()
        results.append(("Screenshot test", True, "Saved to .demo/validation_screenshot.png"))
    except Exception as e:
        results.append(("Screenshot test", False, str(e)))

# 4. ElevenLabs API key valid?
api_key = os.getenv("ELEVENLABS_API_KEY")
if api_key:
    try:
        response = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key},
            timeout=5
        )
        if response.status_code == 200:
            results.append(("ElevenLabs API", True, "Key valid"))
        else:
            results.append(("ElevenLabs API", False, f"Status {response.status_code}"))
    except Exception as e:
        results.append(("ElevenLabs API", False, str(e)))
else:
    results.append(("ElevenLabs API", None, "No API key configured"))

# Print results
print("\nValidation Results:")
for name, passed, message in results:
    if passed is True:
        print(f"  {name}: PASS - {message}")
    elif passed is False:
        print(f"  {name}: FAIL - {message}")
    else:
        print(f"  {name}: SKIP - {message}")

# Overall status
all_passed = all(r[1] is True or r[1] is None for r in results)
if all_passed:
    print("\nAll validations passed!")
else:
    print("\nSome validations failed. Fix issues above before creating demos.")
    sys.exit(1)
PYTHON
```

### Phase 5: Create Config File

Write the final configuration:

```bash
python3 << 'PYTHON'
import yaml
from pathlib import Path

config = {
    "version": 1,
    "project": {
        "name": "{project_name}",
        "tech_stack": "{tech_stack}"
    },
    "app": {
        "base_url": "{base_url}",
        "health_check": "/api/health"  # Optional
    },
    "auth": {
        "strategy": "{auth_strategy}",  # none | cookie | token | oauth
    },
    "test_data": {
        "setup": [],
        "teardown": []
    },
    "recording": {
        "mode": "{recording_mode}",  # local | kubernetes
        "viewport": {
            "width": 1920,
            "height": 1080
        }
    },
    "voice": {
        "provider": "elevenlabs"
    },
    "avatar": {
        "enabled": False,
        "style": "picture-in-picture",
        "position": "bottom-right"
    },
    "output": {
        "upload_to": "gcs"
    }
}

# Add auth-specific config
if config["auth"]["strategy"] == "cookie":
    config["auth"]["login_url"] = "/login"
    config["auth"]["test_user"] = {
        "email": "demo@example.com",
        "password_env": "DEMO_USER_PASSWORD"
    }

# Add seed command if detected
if "{seed_command}":
    config["test_data"]["setup"].append("{seed_command}")

# Add K8s config if using kubernetes mode
if config["recording"]["mode"] == "kubernetes":
    config["recording"]["kubernetes"] = {
        "namespace": "infra",
        "helm_chart": "screenenv-job"
    }

# Create .demo directory
Path(".demo").mkdir(exist_ok=True)

# Write config
with open(".demo/config.yaml", "w") as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

print("Configuration saved to .demo/config.yaml")
print("\nYou can edit this file to customize:")
print("  - Auth settings (login URL, test user)")
print("  - Test data setup/teardown commands")
print("  - Recording preferences")
print("  - Voice settings")
PYTHON
```

### Final Output

```
Demo Creator initialized!

Configuration: .demo/config.yaml
Validation screenshot: .demo/validation_screenshot.png

Ready to create demos! Run /demo to get started.

Tips:
  - View config: cat .demo/config.yaml
  - Re-run init: /demo:init --force
  - Create demo: /demo "feature walkthrough"
```

## Error Handling

**App not accessible:**
- Suggest starting dev server
- Offer to continue with placeholder URL

**Playwright not installed:**
- Provide installation command
- Offer to install automatically

**No credentials:**
- Show how to configure
- Note which features will be limited

**Validation fails:**
- Show specific error
- Suggest fix
- Allow continuing with warnings

---

**Now execute the initialization workflow!**
