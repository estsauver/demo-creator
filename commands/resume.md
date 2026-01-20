---
name: resume
description: Resume a demo creation from the last checkpoint. Use when a demo was interrupted or failed partway through.
---

# Demo Resume Command

You are the Demo Resume handler. Your job is to resume an interrupted or failed demo from its last checkpoint.

## Workflow

### 1. Find Existing Demos

```bash
python3 << 'PYTHON'
import json
from pathlib import Path
from datetime import datetime

demo_dir = Path(".demo")
if not demo_dir.exists():
    print("No demos found. Run /demo to create one.")
    exit(1)

demos = []
for manifest_path in demo_dir.glob("*/manifest.json"):
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)

        demos.append({
            "demo_id": manifest["demo_id"],
            "linear_issue": manifest.get("linear_issue", ""),
            "current_stage": manifest.get("current_stage", 0),
            "completed_stages": manifest.get("completed_stages", []),
            "failed_stages": manifest.get("failed_stages", []),
            "created_at": manifest.get("created_at", ""),
        })
    except Exception as e:
        print(f"Error reading {manifest_path}: {e}")

if not demos:
    print("No demos found. Run /demo to create one.")
    exit(1)

# Sort by created_at descending
demos.sort(key=lambda x: x["created_at"], reverse=True)

print("Available demos:")
print("-" * 60)
for i, demo in enumerate(demos[:10], 1):
    status = "completed" if 9 in demo["completed_stages"] else "in_progress"
    if demo["failed_stages"]:
        status = "failed"

    stage_info = f"Stage {demo['current_stage']}/9"
    if demo["failed_stages"]:
        stage_info += f" (failed: {demo['failed_stages']})"

    print(f"{i}. {demo['demo_id']}")
    print(f"   Linear: {demo['linear_issue']} | {stage_info} | {status}")
    print()
PYTHON
```

### 2. Select Demo to Resume

Use AskUserQuestion if multiple demos available, or auto-select if only one:

```python
AskUserQuestion({
    questions: [{
        question: "Which demo would you like to resume?",
        header: "Demo",
        multiSelect: False,
        options: [
            # Dynamically populated from demos list
            {"label": demo["demo_id"], "description": f"Stage {demo['current_stage']}/9"}
            for demo in demos[:4]
        ]
    }]
})
```

### 3. Load Demo State

```bash
python3 << 'PYTHON'
import sys, json
sys.path.append("plugins/demo-creator")
from utils.manifest import Manifest

demo_id = "{selected_demo_id}"
manifest = Manifest(demo_id)
manifest.load()

print(f"Loaded demo: {demo_id}")
print(f"Linear issue: {manifest.data.get('linear_issue')}")
print(f"Created: {manifest.data.get('created_at')}")
print()
print("Stage Status:")

stage_names = {
    1: "Outline",
    1.5: "Selector Discovery",
    2: "Script Generation",
    3: "Validation",
    4: "Recording",
    5: "Narration",
    6: "Narration Adjustment",
    7: "Audio Generation",
    8: "Video Compositing",
    9: "Upload",
}

completed = manifest.data.get("completed_stages", [])
failed = manifest.data.get("failed_stages", [])
current = manifest.data.get("current_stage", 0)

for stage_num, stage_name in stage_names.items():
    if stage_num in completed:
        status = "completed"
    elif stage_num in failed:
        status = "FAILED"
    elif stage_num == current:
        status = "in_progress"
    elif stage_num < current:
        status = "completed"
    else:
        status = "pending"

    print(f"  Stage {stage_num}: {stage_name} - {status}")

# Show errors if any
if manifest.data.get("errors"):
    print("\nErrors:")
    for error in manifest.data["errors"][-3:]:  # Last 3 errors
        print(f"  Stage {error['stage']}: {error['error_type']}")
        print(f"    {error['error_message'][:100]}")
        if error.get("suggested_fix"):
            print(f"    Fix: {error['suggested_fix']}")
PYTHON
```

### 4. Determine Resume Point

```bash
python3 << 'PYTHON'
import sys
sys.path.append("plugins/demo-creator")
from utils.manifest import Manifest

manifest = Manifest("{demo_id}")
manifest.load()

completed = set(manifest.data.get("completed_stages", []))
failed = manifest.data.get("failed_stages", [])

# Find next stage to run
all_stages = [1, 1.5, 2, 3, 4, 5, 6, 7, 8, 9]
next_stage = None

for stage in all_stages:
    if stage not in completed:
        next_stage = stage
        break

if next_stage is None:
    print("Demo is already complete!")
    print(f"Final video: {manifest.data.get('stage_outputs', {}).get('9', {}).get('video_url', 'Check manifest')}")
    exit(0)

print(f"Resume point: Stage {next_stage}")

# If stage was failed, offer options
if next_stage in failed:
    print(f"Note: Stage {next_stage} previously failed")
    print("Options:")
    print("  1. Retry the failed stage")
    print("  2. Go back and redo previous stage")
    print("  3. Skip and mark as complete (not recommended)")
PYTHON
```

### 5. Handle Resume Options

```python
if failed_stage:
    AskUserQuestion({
        questions: [{
            question: f"Stage {next_stage} failed previously. How would you like to proceed?",
            header: "Action",
            multiSelect: False,
            options: [
                {"label": "Retry stage", "description": "Try the failed stage again"},
                {"label": "Redo previous", "description": "Go back and regenerate from earlier stage"},
                {"label": "View error", "description": "See the error details first"}
            ]
        }]
    })
```

### 6. Resume Pipeline

```bash
python3 << 'PYTHON'
import sys
sys.path.append("plugins/demo-creator")
from utils.manifest import Manifest

manifest = Manifest("{demo_id}")
manifest.load()

# Clear failed status if retrying
if {next_stage} in manifest.data.get("failed_stages", []):
    manifest.data["failed_stages"].remove({next_stage})
    manifest._save()

# Update current stage
manifest.start_stage({next_stage})

print(f"Resuming from Stage {next_stage}")
print("Spawning appropriate agent...")
PYTHON
```

Then spawn the appropriate agent based on the stage:

```python
stage_agents = {
    1: "rough-outline",
    1.5: "discover-selectors",
    2: "detailed-script",
    3: "validate-script",
    4: "record-demo",
    5: "generate-narration",
    6: "adjust-narration",
    7: "generate-audio",
    8: "composite-video",
    9: "upload-to-gcs",
}

Task(
    subagent_type=stage_agents[next_stage],
    description=f"Resume demo stage {next_stage}",
    prompt=f"""
Resume the demo pipeline for:

Demo ID: {demo_id}
Stage: {next_stage}

Read the manifest and previous stage outputs to continue.
"""
)
```

## Error Recovery Options

**If recording failed:**
- Check if app is still accessible
- Verify selectors haven't changed
- Offer to re-run selector discovery

**If audio generation failed:**
- Check API key is valid
- Offer to regenerate narration
- Try with different voice settings

**If upload failed:**
- Check GCS credentials
- Verify bucket exists
- Offer to save locally instead

---

**Now help the user resume their demo!**
