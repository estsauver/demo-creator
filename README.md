# Demo Creator

A Claude Code plugin that automatically creates professional, narrated demo videos from your code.

![Demo Creator](demo-creator-demo.gif)

> **Note**: This plugin was extracted from an internal project and generalized for open source release. It's a working example of a sophisticated multi-stage Claude Code plugin, but **it will need adaptation to work with your specific setup**—your Kubernetes configuration, your app's URL structure, your Playwright selectors, etc.
>
> The good news: just ask Claude to help you bootstrap it. Point Claude at this plugin and your codebase, and it can help you customize the agents, scripts, and configuration to match your environment. That's the whole point of Claude Code plugins—they're meant to be adapted.

## What It Does

Demo Creator is a 9-stage AI pipeline that:

1. **Analyzes** your git branch and recent commits
2. **Generates** a Playwright browser automation script
3. **Validates** the script catches errors before recording
4. **Records** your app running in a Kubernetes environment
5. **Creates** AI narration using ElevenLabs text-to-speech
6. **Composites** the final video with synchronized audio
7. **Uploads** to cloud storage with shareable URLs

The result: polished demo videos ready to embed in PRs, documentation, or Slack.

## Installation

### From GitHub (Recommended)

```bash
# Add the marketplace
claude plugin marketplace add estsauver/demo-creator

# Install the plugin
claude plugin install demo-creator@demo-creator
```

### Manual Installation

Clone the repository and add it as a local plugin:

```bash
git clone https://github.com/estsauver/demo-creator.git
cd demo-creator
claude plugin add .
```

## Requirements

### Environment Variables

```bash
# Required for audio generation (Stage 7)
export ELEVENLABS_API_KEY=sk_your_key_here
export ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Rachel voice (or choose your own)

# Required for cloud upload (Stage 9)
export GCS_BUCKET_NAME=your-bucket-name
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Optional: Kubernetes configuration
export KUBE_CONTEXT=your-k8s-context      # defaults to current context
export DEMO_TARGET_URL=http://localhost:3000  # your app URL
```

### System Dependencies

```bash
# Python packages
pip install requests pyyaml moviepy pydub google-cloud-storage

# System tools
brew install ffmpeg    # macOS
# or
apt install ffmpeg     # Linux
```

### Kubernetes (for browser recording)

The plugin uses Kubernetes Jobs for isolated browser recording:

- A running k8s cluster (k3d, minikube, or cloud)
- Helm 3.x installed
- The `screenenv-job` Helm chart deployed

## Usage

### Quick Start

From Claude Code:

```
# First time? Initialize the plugin for your project:
/demo-creator:init

# Then create a demo:
/demo-creator:create
```

The init command auto-detects your tech stack, running servers, and authentication patterns, then creates a `.demo/config.yaml` file. After that, the create command will guide you through making a demo for your current branch.

### Commands

| Command | Description |
|---------|-------------|
| `/demo-creator:init` | Initialize demo-creator for your project. Auto-detects tech stack, servers, and auth. **Run this first!** |
| `/demo-creator:create` | Full 9-stage pipeline with guided setup |
| `/demo-creator:quick` | Quick demo with auto-detected settings |
| `/demo-creator:resume` | Resume an interrupted demo |
| `/demo-creator:validate` | Validate a script without recording |

> 📝 **Example session**: See [examples/init-and-create-transcript.txt](examples/init-and-create-transcript.txt) for a complete transcript of running `/demo-creator:init` followed by `/demo-creator:create`.

### Example Workflow

```
> /demo-creator:create

Demo Creator: What feature should this demo showcase?
> The new search filtering on the drugs page

Demo Creator: How long should the demo be?
> Standard (1-2 minutes)

[Stage 1] Creating outline...
[Stage 2] Writing Playwright script...
[Stage 3] Validating script...
[Stage 4] Recording demo...
[Stage 5] Generating narration...
[Stage 6] Review narration? (y/n)
[Stage 7] Creating audio...
[Stage 8] Compositing video...
[Stage 9] Uploading to GCS...

✅ Demo complete!
Video: https://storage.googleapis.com/your-bucket/demos/2025/01/ISSUE-123-search-filter/demo_final.mp4
```

## Pipeline Stages

| Stage | Agent | What It Does |
|-------|-------|--------------|
| 1 | `rough-outline` | Analyzes codebase, creates demo outline |
| 2 | `detailed-script` | Writes Playwright Python script |
| 3 | `validate-script` | Dry-run to catch selector errors |
| 4 | `record-demo` | Records browser in k8s Job |
| 5 | `generate-narration` | Creates narration script with timing |
| 6 | `adjust-narration` | User review and editing |
| 7 | `generate-audio` | ElevenLabs text-to-speech |
| 8 | `composite-video` | Merges video + audio |
| 9 | `upload-to-gcs` | Uploads and generates URLs |

## Output Structure

Each demo creates a directory:

```
.demo/ISSUE-123-feature-name/
├── manifest.json           # Pipeline state
├── outline.md              # Demo outline
├── script.py               # Playwright script
├── demo_recording.webm     # Raw video
├── narration.json          # Narration with timestamps
├── narration_audio.mp3     # Generated audio
├── demo_final.mp4          # Final video
└── summary.json            # URLs and metadata
```

## Configuration

### Voice Selection

Find voice IDs at [ElevenLabs Voice Library](https://elevenlabs.io/voice-library):

```bash
# Popular choices
export ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Rachel - professional female
export ELEVENLABS_VOICE_ID=TxGEqnHWrfWFTfGW9XjX  # Josh - clear male
export ELEVENLABS_VOICE_ID=ErXwobaYiN019PkySvjV  # Antoni - calm male
```

Or list available voices:

```bash
python scripts/list_voices.py
```

### Video Quality

Edit `utils/video_compositor.py`:

```python
ffmpeg_params=["-crf", "18"]  # Default: visually lossless
ffmpeg_params=["-crf", "23"]  # Smaller files
```

### Resolution

Set when creating the recording job:

```bash
# In screenenv job configuration
resolution: "1920x1080"  # Default
resolution: "1280x720"   # Smaller files
```

## Troubleshooting

### "Element not found" in validation

Check screenshots in `.demo/{id}/validation_screenshots/` and update selectors in `script.py`.

### Recording job fails

```bash
# Check job status
kubectl get job screenenv-{demo-id} -n infra

# View logs
kubectl logs job/screenenv-{demo-id} -n infra
```

### Audio generation fails

Verify your API key:

```bash
echo $ELEVENLABS_API_KEY
python scripts/check_audio_setup.py
```

### GCS upload permission denied

```bash
# Verify credentials
gcloud auth application-default print-access-token

# Check bucket permissions
gsutil iam get gs://your-bucket-name
```

## Cost Estimates

Per 2-minute demo:
- **ElevenLabs**: ~$0.10-0.15 (narration)
- **GCS Storage**: ~$0.01/month
- **Kubernetes**: Negligible

**Total**: ~$0.15 per demo

## Development

### Running Tests

```bash
cd plugins/demo-creator
pytest tests/
```

### Project Structure

```
demo-creator/
├── .claude-plugin/
│   ├── plugin.json         # Plugin manifest
│   └── marketplace.json    # Marketplace listing
├── agents/                 # Stage agent definitions
├── commands/               # Slash command definitions
├── docs/                   # Internal documentation
├── examples/               # Example demo scripts
├── scripts/                # CLI utilities
│   ├── check_audio_setup.py
│   ├── generate_audio.py
│   ├── list_voices.py
│   └── terminal_demo.py
├── skills/                 # Skill documentation
├── templates/              # Demo templates
├── tests/                  # Test suite
└── utils/                  # Python library
    ├── manifest.py
    ├── elevenlabs_client.py
    ├── gcs_client.py
    ├── screenenv_job.py
    └── video_compositor.py
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [ElevenLabs](https://elevenlabs.io) for text-to-speech API
- [Playwright](https://playwright.dev) for browser automation
- [screenenv](https://github.com/huggingface/screenenv) for headless recording
- [Claude Code](https://claude.ai/code) for the plugin platform
