# Audio Generation - Quick Start

## 30-Second Setup

```bash
# 1. Get ElevenLabs API key (free tier: 10k chars/month)
open https://elevenlabs.io/app/settings/api-keys

# 2. Set credentials
export ELEVENLABS_API_KEY=sk_your_key_here
export ELEVENLABS_VOICE_ID=TxGEqnHWrfWFTfGW9XjX  # Josh (recommended)

# 3. Generate audio
cd /path/to/your/project
python3 plugins/demo-creator/generate_audio.py DEMO-knowledge-engine-pages
```

## Recommended Voices

Choose one and set `ELEVENLABS_VOICE_ID`:

| Voice | ID | Best For |
|-------|----|----|
| Josh | `TxGEqnHWrfWFTfGW9XjX` | Professional tech demos (RECOMMENDED) |
| Rachel | `21m00Tcm4TlvDq8ikWAM` | Clear, professional female |
| Antoni | `ErXwobaYiN019PkySvjV` | Calm, authoritative male |
| Arnold | `VR6AewLTigWG4xSOukaG` | Deep, commanding presence |

## Verify Setup

```bash
python3 plugins/demo-creator/check_audio_setup.py
```

## Explore Voices

```bash
export ELEVENLABS_API_KEY=your_key
python3 plugins/demo-creator/list_voices.py
```

## Output

After generation, you'll have:
- `.demo/DEMO-knowledge-engine-pages/narration_audio.mp3` (56.9s, 192kbps)
- `.demo/DEMO-knowledge-engine-pages/audio_metadata.json`
- `.demo/DEMO-knowledge-engine-pages/audio_segments/*.mp3`

## Cost

- Characters: ~1,500
- Free tier: ✓ (10,000/month limit)
- Paid cost: ~$0.08

## Next Step

After audio generation → Stage 8: Video Compositing

## Full Documentation

See `AUDIO_GENERATION_GUIDE.md` for complete details.
