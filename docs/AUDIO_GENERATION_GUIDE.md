# Audio Generation Guide for Demo Creator

## Overview

This guide explains how to generate high-quality narration audio for demo videos using ElevenLabs text-to-speech API.

## Prerequisites

### 1. ElevenLabs Account Setup

1. **Create Account**: Go to [ElevenLabs](https://elevenlabs.io/) and sign up
2. **Get API Key**:
   - Navigate to Settings → API Keys
   - Create a new API key
   - Copy the key (you won't be able to see it again!)

### 2. Choose a Voice

Run the voice listing script to see available voices:

```bash
# Set your API key
export ELEVENLABS_API_KEY=your_api_key_here

# List available voices
python3 plugins/demo-creator/list_voices.py
```

**Recommended voices for professional narration:**
- **Rachel** (`21m00Tcm4TlvDq8ikWAM`) - Clear, professional female voice
- **Josh** (`TxGEqnHWrfWFTfGW9XjX`) - Professional male voice, great for tech demos
- **Antoni** (`ErXwobaYiN019PkySvjV`) - Calm, authoritative male voice
- **Arnold** (`VR6AewLTigWG4xSOukaG`) - Deep, commanding presence

### 3. Install Dependencies

```bash
# Install required Python packages
pip install pydub requests

# Install ffmpeg (required by pydub for audio processing)
# macOS:
brew install ffmpeg

# Linux:
sudo apt-get install ffmpeg

# Windows:
# Download from https://ffmpeg.org/download.html
```

## Environment Configuration

Add these variables to your `.env` file or export them in your shell:

```bash
# Required: Your ElevenLabs API key
export ELEVENLABS_API_KEY=sk_your_api_key_here

# Required: Voice ID to use for narration
export ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Rachel (recommended)

# Optional: Alternative voices
# export ELEVENLABS_VOICE_ID=TxGEqnHWrfWFTfGW9XjX  # Josh
# export ELEVENLABS_VOICE_ID=ErXwobaYiN019PkySvjV  # Antoni
```

## Usage

### Generate Audio for a Demo

```bash
cd /path/to/your/project

# Generate audio for the Knowledge Engine Pages demo
python3 plugins/demo-creator/generate_audio.py DEMO-knowledge-engine-pages
```

### What Happens

The script will:

1. **Load narration data** from `.demo/DEMO-knowledge-engine-pages/narration.json`
2. **Generate individual segments**:
   - Calls ElevenLabs API for each narration segment
   - Saves segment audio to `.demo/DEMO-knowledge-engine-pages/audio_segments/segment_XXX.mp3`
3. **Concatenate with timing**:
   - Adds silence between segments to match timing from narration.json
   - Ensures audio sync with video transitions
4. **Export final audio**:
   - Saves to `.demo/DEMO-knowledge-engine-pages/narration_audio.mp3`
   - 192 kbps MP3, high-quality VBR encoding
5. **Save metadata**:
   - Records generation details in `.demo/DEMO-knowledge-engine-pages/audio_metadata.json`

### Expected Output

```
=== Audio Generation for DEMO-knowledge-engine-pages ===

Voice ID: 21m00Tcm4TlvDq8ikWAM

Loading narration data...
  Total segments: 10
  Expected duration: 56.92s

Generating audio segments...
  Generating segment 1: Welcome to the your application...
    Generated: 6.45s (expected: 6.50s)
  Generating segment 2: You can search and filter diseases by various...
    Generated: 5.52s (expected: 5.50s)
  ...

Concatenating audio segments with timing...
  Added segment 1: 6.45s @ 0.00s
  Added 50ms silence before segment 2
  Added segment 2: 5.52s @ 6.50s
  ...

Exporting final audio to: .demo/DEMO-knowledge-engine-pages/narration_audio.mp3

=== Generation Complete ===
  Output: .demo/DEMO-knowledge-engine-pages/narration_audio.mp3
  Duration: 56.89s (expected: 56.92s)
  Difference: -0.03s
  Metadata saved to: .demo/DEMO-knowledge-engine-pages/audio_metadata.json

Success! Audio generated: .demo/DEMO-knowledge-engine-pages/narration_audio.mp3
```

## Output Files

After generation, you'll have:

```
.demo/DEMO-knowledge-engine-pages/
├── narration.json              # Input: Narration script with timing
├── narration_audio.mp3         # Output: Final audio track
├── audio_metadata.json         # Output: Generation metadata
└── audio_segments/             # Output: Individual segment files
    ├── segment_001.mp3
    ├── segment_002.mp3
    ├── segment_003.mp3
    └── ...
```

## Quality Settings

The script uses optimal settings for professional narration:

- **Stability**: 0.5 (balanced, natural variation)
- **Similarity Boost**: 0.75 (high voice quality matching)
- **Model**: `eleven_multilingual_v2` (latest, highest quality)
- **Bitrate**: 192 kbps (high-quality MP3)
- **Encoding**: VBR with highest quality preset (`-q:a 0`)

## Troubleshooting

### API Key Not Set

```
ERROR: ELEVENLABS_API_KEY environment variable not set.
```

**Solution**: Export your API key:
```bash
export ELEVENLABS_API_KEY=your_api_key_here
```

### Voice ID Not Set

```
ERROR: ELEVENLABS_VOICE_ID environment variable not set.
```

**Solution**: Choose a voice and export the ID:
```bash
export ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
```

### pydub Not Installed

```
ImportError: pydub is required for audio concatenation.
```

**Solution**: Install pydub and ffmpeg:
```bash
pip install pydub
brew install ffmpeg  # macOS
```

### API Rate Limits

If you hit rate limits, the script will fail with an API error. Solutions:

1. **Wait**: Free tier has daily limits
2. **Upgrade**: Consider ElevenLabs paid plan for higher limits
3. **Retry**: Wait a few minutes and run again

### Audio Too Long/Short

```
WARNING: Duration differs by more than 5 seconds!
```

This usually means:

1. **Text is too long**: ElevenLabs takes longer to speak than expected
   - Solution: Edit narration.json to be more concise
2. **Timing issues**: Segment timing in narration.json is off
   - Solution: Review segment start/end times

## API Costs

ElevenLabs pricing (as of 2024):

- **Free Tier**: 10,000 characters/month
- **Starter**: $5/month for 30,000 characters
- **Creator**: $22/month for 100,000 characters

**Estimated costs for this demo:**
- Total characters: ~1,500 (10 segments averaging 150 chars)
- Free tier: Plenty of capacity
- Cost on paid tier: ~$0.08 (at Creator pricing)

## Voice Customization

To fine-tune voice settings, edit `generate_audio.py`:

```python
result = client.generate_audio(
    text=text,
    output_path=str(output_file),
    stability=0.5,        # 0-1: Lower = more expressive, Higher = more stable
    similarity_boost=0.75, # 0-1: Higher = closer to original voice
)
```

**Stability:**
- 0.3-0.5: More expressive, natural variation (good for storytelling)
- 0.5-0.7: Balanced (recommended for narration)
- 0.7-1.0: Very stable, consistent (good for formal content)

**Similarity Boost:**
- 0.5-0.7: More creative interpretation
- 0.7-0.85: Balanced (recommended)
- 0.85-1.0: Maximum fidelity to original voice

## Next Steps

After generating audio:

1. **Review audio**: Listen to `narration_audio.mp3`
2. **Check timing**: Ensure audio aligns with video scenes
3. **Proceed to Stage 8**: Video compositing
   - Combine video recording with narration audio
   - Add fade effects and transitions
   - Export final demo video

## Support

For issues with:
- **ElevenLabs API**: Check [ElevenLabs Documentation](https://docs.elevenlabs.io/)
- **This script**: Check error messages and traceback
- **Audio quality**: Try different voices or adjust stability/similarity settings
