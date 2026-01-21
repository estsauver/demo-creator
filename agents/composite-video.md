---
name: composite-video
description: >
  Composite video and audio into final demo video with optional subtitles.
  ALWAYS delegate Stage 8 compositing to this agent - ffmpeg operations produce verbose output that should stay isolated.
tools: Read, Write, Bash, Grep
model: sonnet
---

# Stage 8: Video Compositing Agent

You are the Video Compositing Agent - merge video and audio into the final demo.

## Your Mission

Create the final demo video by combining:
- Original video recording from Stage 4
- Generated narration audio from Stage 7
- Optional subtitle track from Stage 5
- Output as high-quality MP4

## Workflow

### 1. Load Context

```bash
python3 << 'PYTHON'
import sys, json
sys.path.append("plugins/demo-creator")
from utils.manifest import Manifest

manifest = Manifest("{demo_id}")
manifest.load()

print(f"Demo ID: {manifest.data['demo_id']}")
print(f"Video: {manifest.data['stages'][3].get('video_path')}")
print(f"Audio: {manifest.data['stages'][6].get('audio_path')}")
print(f"Subtitles: {manifest.data['stages'][4].get('srt_path')}")
PYTHON
```

### 2. Verify Dependencies

```bash
# Install moviepy if needed
pip install -q moviepy

# Verify ffmpeg is available
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ ERROR: ffmpeg not found"
    echo "   Install: apt-get install ffmpeg (Linux) or brew install ffmpeg (Mac)"
    exit 1
fi

echo "✅ ffmpeg available: $(ffmpeg -version | head -1)"
```

### 3. Load Video and Audio

```bash
python3 << 'PYTHON'
import sys
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
sys.path.append("plugins/demo-creator")
from utils.manifest import Manifest

manifest = Manifest("{demo_id}")
manifest.load()

# Load video
video_path = manifest.get_file_path(manifest.data['stages'][3]['video_path'])
video = VideoFileClip(video_path)

print(f"✅ Video loaded: {video.duration:.2f}s, {video.size}")

# Load audio
audio_path = manifest.get_file_path(manifest.data['stages'][6]['audio_path'])
audio = AudioFileClip(audio_path)

print(f"✅ Audio loaded: {audio.duration:.2f}s")

# Check duration compatibility
duration_diff = abs(audio.duration - video.duration)

if duration_diff > 10.0:
    print(f"❌ TIMING MISMATCH: Audio ({audio.duration:.2f}s) vs Video ({video.duration:.2f}s)")
    print(f"   Difference: {duration_diff:.2f}s (too large for speed adjustment)")
    print("")
    print("🔧 Auto-adjusting script timing to match audio duration...")

    # Close resources before re-recording
    video.close()
    audio.close()

    # This will trigger script adjustment and re-recording
    # See "Auto-Timing Adjustment" section below
    import sys
    sys.exit(100)  # Special exit code for timing adjustment needed

elif duration_diff > 2.0:
    print(f"⚠️ Minor timing difference: {duration_diff:.2f}s")
    print(f"   Will use {1 + (duration_diff / max(video.duration, audio.duration)):.2f}x speed adjustment")
    # Continue with minor speed adjustment

else:
    print(f"✅ Timing compatible: difference {duration_diff:.2f}s")

# Store for next step
video_duration = video.duration
audio_duration = audio.duration

video.close()
audio.close()

# Save metadata
import json
with open(manifest.get_file_path("composite_metadata.json"), "w") as f:
    json.dump({
        "video_duration": video_duration,
        "audio_duration": audio_duration,
        "size": list(video.size)
    }, f, indent=2)

print("✅ Media files loaded successfully")
PYTHON
```

### 4. Composite Video with Audio

```bash
python3 << 'PYTHON'
import sys
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
sys.path.append("plugins/demo-creator")
from utils.manifest import Manifest

manifest = Manifest("{demo_id}")
manifest.load()

print("🎬 Starting video composition...")

# Load video
video_path = manifest.get_file_path(manifest.data['stages'][3]['video_path'])
video = VideoFileClip(video_path)

# Load narration audio
narration_path = manifest.get_file_path(manifest.data['stages'][6]['audio_path'])
narration_audio = AudioFileClip(narration_path)

# Trim audio if longer than video
if narration_audio.duration > video.duration:
    narration_audio = narration_audio.subclip(0, video.duration)

# Check if video has original audio
if video.audio is not None:
    print("  Mixing narration with original video audio...")
    # Mix original audio (reduced volume) with narration
    original_audio = video.audio.volumex(0.3)  # 30% volume
    combined_audio = CompositeAudioClip([original_audio, narration_audio])
else:
    print("  No original audio, using narration only...")
    combined_audio = narration_audio

# Set audio to video
final_video = video.set_audio(combined_audio)

# Export final video
output_path = manifest.get_file_path("demo_final.mp4")

print(f"  Exporting to: {output_path}")

final_video.write_videofile(
    output_path,
    codec="libx264",
    audio_codec="aac",
    fps=video.fps,
    preset="medium",  # balance between speed and quality
    bitrate="5000k",  # 5 Mbps video bitrate
    audio_bitrate="192k",
    threads=4,
    logger=None  # Suppress moviepy progress bars
)

# Clean up
final_video.close()
video.close()
narration_audio.close()
if video.audio:
    original_audio.close()

print("✅ Video composition complete")
PYTHON
```

### 5. Embed Subtitle Track

Embed subtitles as a toggleable track in the MP4 container (QuickTime: View → Subtitles → English):

```bash
python3 << 'PYTHON'
import sys, os, shutil, subprocess
sys.path.append("plugins/demo-creator")
from utils.manifest import Manifest

manifest = Manifest("{demo_id}")
manifest.load()

final_path = manifest.get_file_path("demo_final.mp4")
srt_path = manifest.get_file_path(manifest.data['stages'][4]['srt_path'])
temp_path = manifest.get_file_path("demo_final_temp.mp4")

# Check if SRT exists
if not os.path.exists(srt_path):
    print("⚠️ No SRT file found, skipping subtitle embedding")
    sys.exit(0)

# Rename original to temp
shutil.move(final_path, temp_path)

# Embed subtitle track using mov_text codec (MP4 compatible)
cmd = [
    "ffmpeg", "-y",
    "-i", str(temp_path),       # Video+audio input
    "-i", str(srt_path),        # Subtitle input
    "-c:v", "copy",             # Copy video (no re-encode)
    "-c:a", "copy",             # Copy audio (no re-encode)
    "-c:s", "mov_text",         # MOV text subtitles
    "-metadata:s:s:0", "language=eng",
    "-metadata:s:s:0", "title=English",
    str(final_path)
]

print("📝 Embedding subtitle track...")
result = subprocess.run(cmd, capture_output=True, text=True)

if result.returncode == 0:
    os.remove(temp_path)
    print("✅ Subtitle track embedded")

    # Verify subtitle track exists
    probe_cmd = ["ffprobe", "-v", "error", "-show_entries",
                 "stream=codec_type,codec_name", "-of", "csv=p=0", str(final_path)]
    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
    print(f"   Streams: {probe_result.stdout.strip()}")
    print("")
    print("📺 Player compatibility:")
    print("   QuickTime: View → Subtitles → English")
    print("   VLC: Subtitle → Sub Track → English")
    print("   YouTube/Vimeo: Auto-detected on upload")
else:
    # Restore original if failed
    shutil.move(temp_path, final_path)
    print(f"⚠️ Subtitle embedding failed: {result.stderr}")
    print("   Video available without subtitles")

# Also create WebVTT for HTML5 video compatibility
vtt_path = manifest.get_file_path("final_demo.vtt")
vtt_cmd = ["ffmpeg", "-y", "-i", str(srt_path), str(vtt_path)]
vtt_result = subprocess.run(vtt_cmd, capture_output=True, text=True)

if vtt_result.returncode == 0:
    print(f"✅ WebVTT also created for HTML5: {vtt_path.name}")
PYTHON
```

### 6. Verify Final Video

```bash
python3 << 'PYTHON'
import sys, os
from moviepy.editor import VideoFileClip
sys.path.append("plugins/demo-creator")
from utils.manifest import Manifest

manifest = Manifest("{demo_id}")
manifest.load()

# Load final video
final_path = manifest.get_file_path("demo_final.mp4")

if not os.path.exists(final_path):
    print(f"❌ ERROR: Final video not found at {final_path}")
    sys.exit(1)

video = VideoFileClip(final_path)

print("=" * 60)
print("FINAL VIDEO VERIFICATION")
print("=" * 60)
print(f"Path: {final_path}")
print(f"Duration: {video.duration:.2f}s")
print(f"Resolution: {video.size}")
print(f"FPS: {video.fps}")
print(f"Has audio: {video.audio is not None}")
if video.audio:
    print(f"Audio duration: {video.audio.duration:.2f}s")

file_size_mb = os.path.getsize(final_path) / (1024 * 1024)
print(f"File size: {file_size_mb:.2f} MB")
print("=" * 60)

video.close()

print("✅ Final video verification complete")
PYTHON
```

### 7. Update Manifest

```bash
python3 << 'PYTHON'
import sys, os
from moviepy.editor import VideoFileClip
sys.path.append("plugins/demo-creator")
from utils.manifest import Manifest

manifest = Manifest("{demo_id}")
manifest.load()

# Get final video metadata
final_path = manifest.get_file_path("demo_final.mp4")
video = VideoFileClip(final_path)
file_size_mb = os.path.getsize(final_path) / (1024 * 1024)

manifest.complete_stage(8, {
    "composite_status": "completed",
    "final_video_path": "demo_final.mp4",
    "duration_seconds": video.duration,
    "resolution": list(video.size),
    "fps": video.fps,
    "file_size_mb": round(file_size_mb, 2),
    "has_audio": video.audio is not None,
    "subtitles_included": os.getenv("DEMO_INCLUDE_SUBTITLES", "false").lower() == "true"
})

video.close()

print(f"✅ Stage 8 complete: Video composited ({video.duration:.2f}s, {file_size_mb:.2f} MB)")
PYTHON
```

## Compositing Options

**Video Codec Settings:**
- Codec: `libx264` (H.264) - widely compatible
- Preset: `medium` (balance speed/quality)
- Bitrate: `5000k` (5 Mbps) - high quality
- Alternative: `ultrafast` preset for quick testing

**Audio Mixing:**
- Original video audio: 30% volume (background)
- Narration: 100% volume (primary)
- Can adjust mix levels via `volumex()` parameter

**Subtitle Styling:**
- Font size: 24pt
- Color: White with black outline
- Position: Bottom center (default)
- Can customize via ffmpeg force_style parameter

## Auto-Timing Adjustment

If the timing check (Step 3) exits with code 100, it means audio/video timing mismatch is >10 seconds. Automatically adjust the script timing:

```bash
python3 << 'PYTHON'
import sys, re
sys.path.append("plugins/demo-creator")
from utils.manifest import Manifest

manifest = Manifest("{demo_id}")
manifest.load()

# Load durations from metadata
import json
with open(manifest.get_file_path("composite_metadata.json")) as f:
    meta = json.load(f)

video_duration = meta["video_duration"]
audio_duration = meta["audio_duration"]

# Calculate how much additional time needed
additional_time = audio_duration - video_duration

print(f"Video: {video_duration:.2f}s")
print(f"Audio: {audio_duration:.2f}s")
print(f"Need to add: {additional_time:.2f}s to video")

# Load script
script_path = manifest.get_file_path(manifest.data['stages'][1]['script_path'])
with open(script_path) as f:
    script_content = f.read()

# Count existing sleep calls
sleep_matches = re.findall(r'time\.sleep\((\d+(?:\.\d+)?)\)', script_content)
total_sleep = sum(float(s) for s in sleep_matches)
num_sleeps = len(sleep_matches)

print(f"Current script has {num_sleeps} sleep calls totaling {total_sleep:.2f}s")

# Distribute additional time across existing sleeps
if num_sleeps > 0:
    additional_per_sleep = additional_time / num_sleeps

    print(f"Adding {additional_per_sleep:.2f}s to each sleep call...")

    # Replace each sleep with adjusted value
    def adjust_sleep(match):
        current = float(match.group(1))
        new_value = current + additional_per_sleep
        return f'time.sleep({new_value:.2f})'

    script_content = re.sub(
        r'time\.sleep\((\d+(?:\.\d+)?)\)',
        adjust_sleep,
        script_content
    )

    # Save adjusted script
    with open(script_path, 'w') as f:
        f.write(script_content)

    print(f"✅ Script adjusted: added {additional_time:.2f}s across {num_sleeps} points")
else:
    print("⚠️ No sleep calls found in script - cannot auto-adjust")
    print("   Manual adjustment needed")
    sys.exit(1)
PYTHON
```

After adjustment, re-run validation and recording:

```bash
echo ""
echo "🔄 Re-validating adjusted script..."

# Spawn validate-script agent to verify changes
# (This will be handled by the orchestrator)
```

Then return to Step 3 (Load Video and Audio) to verify new timing.

## Error Handling

**moviepy import errors:**
```bash
pip install --upgrade moviepy
pip install imageio-ffmpeg
```

**ffmpeg codec errors:**
- Ensure ffmpeg is compiled with libx264 and aac support
- Check: `ffmpeg -codecs | grep h264`

**Memory errors with large videos:**
- Process video in chunks
- Reduce video resolution/bitrate
- Use `preset=ultrafast` for faster processing

**Audio/video sync issues:**
- Verify timestamps in narration script
- Check audio duration vs. video duration
- May need to adjust narration timing in Stage 6

## Success Criteria

✅ Compositing succeeds if:
- Final MP4 file is created
- Video has both picture and audio
- Audio is properly synchronized
- File size is reasonable (<100MB for 2min video)
- Video plays correctly in media players

❌ Compositing fails if:
- ffmpeg errors during export
- Final file is missing or corrupt
- Audio/video severely out of sync
- File size is excessive or zero bytes

## Environment Variables

```bash
DEMO_INCLUDE_SUBTITLES=true   # Optional: burn in subtitles
```

---

**Now execute the video compositing workflow.**
