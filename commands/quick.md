---
description: Quick demo creation with minimal configuration. Auto-detects everything and runs with sensible defaults. Use for fast, simple demos.
---

# Demo Quick Command

You are the Quick Demo handler. Create a demo with minimal user input using smart defaults.

## When to Use

- Simple feature demos
- Quick feature walkthroughs
- When user wants minimal interaction
- Time-sensitive demo needs

## Workflow

### 1. Parse Quick Command Args

Quick command can be invoked as:
- `/demo:quick` - Auto-detect everything
- `/demo:quick "feature description"` - With description
- `/demo:quick --terminal` - Terminal demo
- `/demo:quick --duration=60s` - With duration

```python
import sys
import re

args = "{args}"  # From command invocation

# Parse options
is_terminal = "--terminal" in args
duration_match = re.search(r'--duration=(\d+)s?', args)
duration = int(duration_match.group(1)) if duration_match else 60

# Extract description (anything not a flag)
description = re.sub(r'--\w+(=\S+)?', '', args).strip().strip('"\'')

print(f"Quick demo settings:")
print(f"  Type: {'terminal' if is_terminal else 'browser'}")
print(f"  Duration: {duration}s")
print(f"  Description: {description or '(auto-detect)'}")
```

### 2. Auto-Detect Feature

```bash
python3 << 'PYTHON'
import subprocess
import re

# Get git context
branch = subprocess.run(
    ["git", "branch", "--show-current"],
    capture_output=True, text=True
).stdout.strip()

sha = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    capture_output=True, text=True
).stdout.strip()[:7]

# Extract Linear issue
linear_match = re.search(r'([A-Z]+-\d+)', branch, re.IGNORECASE)
linear_issue = linear_match.group(1) if linear_match else None

# Extract feature name from branch
feature = branch
feature = re.sub(r'^[^/]+/', '', feature)  # Remove user prefix
feature = re.sub(r'[A-Z]+-\d+-', '', feature, flags=re.IGNORECASE)
feature = feature.replace('-', ' ').replace('_', ' ')

print(f"Auto-detected:")
print(f"  Branch: {branch}")
print(f"  SHA: {sha}")
print(f"  Linear: {linear_issue or 'None'}")
print(f"  Feature: {feature}")

# Get recent changes
recent_files = subprocess.run(
    ["git", "diff", "--name-only", "HEAD~5"],
    capture_output=True, text=True
).stdout.strip().split('\n')

# Identify likely demo pages from changed files
demo_pages = []
for f in recent_files:
    if 'page' in f.lower() or 'route' in f.lower():
        # Extract page path
        match = re.search(r'pages?/(.+?)\.(tsx?|jsx?)', f)
        if match:
            page = '/' + match.group(1).replace('[', ':').replace(']', '')
            demo_pages.append(page)

if demo_pages:
    print(f"  Likely pages: {demo_pages[:3]}")
PYTHON
```

### 3. Generate Demo ID

```bash
python3 << 'PYTHON'
import subprocess
import re
import time

branch = subprocess.run(
    ["git", "branch", "--show-current"],
    capture_output=True, text=True
).stdout.strip()

# Extract Linear issue
linear_match = re.search(r'([A-Z]+-\d+)', branch, re.IGNORECASE)
linear_prefix = linear_match.group(1) if linear_match else "DEMO"

# Short timestamp
timestamp = int(time.time()) % 100000

demo_id = f"{linear_prefix}-quick-{timestamp}"
print(f"Demo ID: {demo_id}")
PYTHON
```

### 4. Create Minimal Manifest

```bash
python3 << 'PYTHON'
import sys, subprocess
sys.path.append("plugins/demo-creator")
from utils.manifest import Manifest

demo_id = "{demo_id}"

# Get git info
branch = subprocess.run(
    ["git", "branch", "--show-current"],
    capture_output=True, text=True
).stdout.strip()

sha = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    capture_output=True, text=True
).stdout.strip()[:7]

# Initialize manifest
manifest = Manifest(demo_id)
manifest.initialize(
    git_branch=branch,
    git_sha=sha,
)

# Add quick mode flag
manifest.data["quick_mode"] = True
manifest.data["target_duration"] = {duration}
manifest._save()

print(f"Manifest created: .demo/{demo_id}/manifest.json")
PYTHON
```

### 5. Generate Quick Outline

For quick mode, generate a simple 3-scene outline:

```bash
python3 << 'PYTHON'
import sys
sys.path.append("plugins/demo-creator")
from utils.manifest import Manifest

demo_id = "{demo_id}"
manifest = Manifest(demo_id)
manifest.load()

feature = "{feature_name}"
duration = {duration}

# Calculate scene durations
scene_duration = duration // 3

outline = f"""# Quick Demo: {feature}

**Mode:** Quick (minimal configuration)
**Target Duration:** {duration} seconds

## Demo Flow

### Scene 1: Introduction ({scene_duration}s)
Navigate to the feature and show the initial state.

### Scene 2: Core Action ({scene_duration}s)
Demonstrate the main functionality.

### Scene 3: Result ({scene_duration}s)
Show the outcome and wrap up.

## Notes
- Auto-generated outline for quick demo
- Edit .demo/{demo_id}/outline.md to customize
"""

with open(manifest.get_file_path("outline.md"), "w") as f:
    f.write(outline)

manifest.complete_stage(1, {
    "outline_path": "outline.md",
    "quick_mode": True,
})

print("Quick outline generated")
PYTHON
```

### 6. Fast-Track Pipeline

Skip selector discovery for quick mode and go straight to script generation:

```python
print("Starting quick pipeline...")
print("  [1/9] Outline: Generated (quick mode)")
print("  [2/9] Script: Generating...")

Task(
    subagent_type="detailed-script",
    model="haiku",  # Use fast model for quick mode
    description="Generate quick demo script",
    prompt=f"""
Quick demo script generation for:

Demo ID: {demo_id}
Feature: {feature_name}
Duration: {duration}s

This is quick mode - generate a simple 3-scene script:
1. Navigate to feature
2. Perform main action
3. Show result

Use text-based selectors for resilience. Keep it simple.
"""
)
```

### 7. Continue Pipeline with Minimal Interaction

After script generation, continue through stages automatically:
- Validation: Run once, proceed on success
- Recording: Use local mode
- Narration: Generate automatically, skip adjustment
- Audio: Generate in parallel if possible
- Composite: Use defaults
- Upload: To configured destination

```python
# Skip narration adjustment (stage 6) in quick mode
manifest.data["skip_stages"] = [6]  # Skip adjustment
manifest._save()

print("Quick mode enabled:")
print("  - Narration adjustment: Skipped")
print("  - User interaction: Minimal")
print("  - Estimated time: 5-8 minutes")
```

### 8. Report Result

```python
print()
print("=" * 50)
print("QUICK DEMO COMPLETE")
print("=" * 50)
print()
print(f"Demo ID: {demo_id}")
print(f"Duration: {actual_duration}s")
print()
print(f"Video: {video_url}")
print()
print("To customize, run /demo with full options.")
```

## Quick Mode Optimizations

| Optimization | Effect |
|--------------|--------|
| Skip Stage 6 | No narration review needed |
| Use haiku model | Faster generation |
| Simple 3-scene | Less recording time |
| Local recording | No K8s overhead |
| Default voice | No voice selection |
| Auto-upload | Immediate URL |

---

**Now create a quick demo!**
