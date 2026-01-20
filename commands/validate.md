---
name: validate
description: Validate demo-creator setup without creating a demo. Checks app accessibility, credentials, and dependencies.
---

# Demo Validate Command

You are the Demo Validate handler. Run comprehensive validation of the demo-creator setup.

## Workflow

### 1. Load Configuration

```bash
python3 << 'PYTHON'
import yaml
from pathlib import Path

config_path = Path(".demo/config.yaml")

if not config_path.exists():
    print("No configuration found!")
    print("Run /demo:init first to set up demo-creator.")
    exit(1)

with open(config_path) as f:
    config = yaml.safe_load(f)

print("Configuration loaded")
print(f"  Project: {config.get('project', {}).get('name', 'Unknown')}")
print(f"  Tech stack: {config.get('project', {}).get('tech_stack', 'Unknown')}")
print(f"  Base URL: {config.get('app', {}).get('base_url', 'Not set')}")
print(f"  Recording mode: {config.get('recording', {}).get('mode', 'local')}")
PYTHON
```

### 2. Check Application Accessibility

```bash
python3 << 'PYTHON'
import yaml
import requests

with open(".demo/config.yaml") as f:
    config = yaml.safe_load(f)

base_url = config.get("app", {}).get("base_url", "http://localhost:3000")
health_check = config.get("app", {}).get("health_check")

print("\n1. Application Accessibility")
print("-" * 40)

# Check base URL
try:
    response = requests.get(base_url, timeout=5)
    print(f"   Base URL ({base_url}): PASS (status {response.status_code})")
except requests.exceptions.ConnectionError:
    print(f"   Base URL ({base_url}): FAIL (connection refused)")
    print(f"      Make sure your app is running!")
except requests.exceptions.Timeout:
    print(f"   Base URL ({base_url}): FAIL (timeout)")
except Exception as e:
    print(f"   Base URL ({base_url}): FAIL ({e})")

# Check health endpoint if configured
if health_check:
    health_url = f"{base_url}{health_check}"
    try:
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            print(f"   Health check ({health_check}): PASS")
        else:
            print(f"   Health check ({health_check}): WARN (status {response.status_code})")
    except Exception as e:
        print(f"   Health check ({health_check}): FAIL ({e})")
PYTHON
```

### 3. Check Dependencies

```bash
python3 << 'PYTHON'
import subprocess
import sys

print("\n2. Dependencies")
print("-" * 40)

# Check Python packages
packages = {
    "playwright": "Browser automation",
    "moviepy": "Video compositing",
    "requests": "HTTP requests",
    "yaml": "Configuration parsing (pyyaml)",
}

for package, description in packages.items():
    try:
        if package == "yaml":
            import yaml
        else:
            __import__(package)
        print(f"   {package}: PASS ({description})")
    except ImportError:
        print(f"   {package}: FAIL (not installed)")
        print(f"      pip install {package if package != 'yaml' else 'pyyaml'}")

# Check Playwright browsers
print()
try:
    result = subprocess.run(
        ["playwright", "install", "--dry-run", "chromium"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if "already installed" in result.stdout or result.returncode == 0:
        print("   Playwright Chromium: PASS")
    else:
        print("   Playwright Chromium: WARN (may need installation)")
        print("      playwright install chromium")
except FileNotFoundError:
    print("   Playwright CLI: FAIL (not in PATH)")
except Exception as e:
    print(f"   Playwright: WARN ({e})")

# Check ffmpeg
try:
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
    print("   ffmpeg: PASS")
except FileNotFoundError:
    print("   ffmpeg: FAIL (not installed)")
    print("      brew install ffmpeg  # macOS")
    print("      apt install ffmpeg   # Linux")
PYTHON
```

### 4. Check Credentials

```bash
python3 << 'PYTHON'
import sys
sys.path.append("plugins/demo-creator")
from utils.credentials import load_credentials, validate_elevenlabs_key

print("\n3. Credentials")
print("-" * 40)

creds = load_credentials()
status = creds.get_status()

for name, valid in status.items():
    status_str = "PASS" if valid else "FAIL (not configured)"
    importance = "required" if name in ["elevenlabs", "gcs"] else "optional"
    print(f"   {name}: {status_str} ({importance})")

# Validate ElevenLabs if configured
if status["elevenlabs"]:
    print()
    print("   Validating ElevenLabs API key...")
    if validate_elevenlabs_key():
        print("   ElevenLabs API: PASS (key valid)")
    else:
        print("   ElevenLabs API: FAIL (key invalid)")
PYTHON
```

### 5. Check Recording Capability

```bash
python3 << 'PYTHON'
import yaml
from pathlib import Path

with open(".demo/config.yaml") as f:
    config = yaml.safe_load(f)

recording_mode = config.get("recording", {}).get("mode", "local")

print("\n4. Recording Capability")
print("-" * 40)

if recording_mode == "local":
    print("   Mode: Local (Playwright)")

    # Try to take a screenshot
    base_url = config.get("app", {}).get("base_url", "http://localhost:3000")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(base_url, timeout=10000)

            # Take test screenshot
            Path(".demo").mkdir(exist_ok=True)
            page.screenshot(path=".demo/validation_screenshot.png")
            browser.close()

        print("   Screenshot test: PASS")
        print("   Saved: .demo/validation_screenshot.png")

    except Exception as e:
        print(f"   Screenshot test: FAIL ({e})")

elif recording_mode == "kubernetes":
    print("   Mode: Kubernetes")

    import subprocess

    # Check kubectl
    try:
        result = subprocess.run(
            ["kubectl", "version", "--client", "-o", "json"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            print("   kubectl: PASS")
        else:
            print("   kubectl: FAIL")
    except Exception as e:
        print(f"   kubectl: FAIL ({e})")

    # Check Helm
    try:
        result = subprocess.run(
            ["helm", "version", "--short"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            print("   helm: PASS")
        else:
            print("   helm: FAIL")
    except Exception as e:
        print(f"   helm: FAIL ({e})")
PYTHON
```

### 6. Summary

```bash
python3 << 'PYTHON'
print("\n" + "=" * 40)
print("VALIDATION SUMMARY")
print("=" * 40)

# Count passes and fails from previous checks
# This is a simplified summary - in practice, collect results

print()
print("If all checks pass: Ready to create demos!")
print("If some checks fail: Fix the issues above first.")
print()
print("Quick fixes:")
print("  - App not running: Start your dev server")
print("  - Missing packages: pip install playwright moviepy")
print("  - Missing credentials: Edit ~/.claude/demo-credentials.yaml")
print("  - Playwright not installed: playwright install chromium")
PYTHON
```

---

**Now run the validation checks!**
