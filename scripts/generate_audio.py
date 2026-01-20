#!/usr/bin/env python3
"""
Audio Generation Utility Library for Demo Creator

This module provides utility functions for generating narration audio using ElevenLabs API.

IMPORTANT: This should be called via the generate-audio agent, NOT directly!
Use: Task(subagent_type="demo-creator:generate-audio", ...)

Direct CLI usage (for testing only):
    python3 generate_audio.py DEMO-knowledge-engine-pages

Environment Variables Required:
    ELEVENLABS_API_KEY: Your ElevenLabs API key
    ELEVENLABS_VOICE_ID: Voice ID to use (e.g., Josh, Rachel)

Output:
    .demo/{demo_id}/narration_audio.mp3 - Final concatenated audio
    .demo/{demo_id}/audio_segments/ - Individual segment files
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.elevenlabs_client import ElevenLabsClient, check_api_key


def load_narration(demo_id: str) -> Dict[str, Any]:
    """Load narration data from narration.json"""
    narration_path = Path(f".demo/{demo_id}/narration.json")

    if not narration_path.exists():
        raise FileNotFoundError(f"Narration file not found: {narration_path}")

    with open(narration_path, 'r') as f:
        return json.load(f)


def generate_segment_audio(
    client: ElevenLabsClient,
    segment: Dict[str, Any],
    demo_id: str,
    output_dir: Path,
) -> Dict[str, Any]:
    """
    Generate audio for a single narration segment.

    Args:
        client: ElevenLabs client
        segment: Segment data with 'text', 'start_time', 'end_time'
        demo_id: Demo identifier
        output_dir: Directory to save audio files

    Returns:
        Dict with segment info and generated audio metadata
    """
    segment_id = segment['segment_id']
    text = segment['text']

    # Output file path
    output_file = output_dir / f"segment_{segment_id:03d}.mp3"

    print(f"  Generating segment {segment_id}: {text[:50]}...")

    # Generate audio
    result = client.generate_audio(
        text=text,
        output_path=str(output_file),
        stability=0.5,  # Good balance for narration
        similarity_boost=0.75,  # High quality voice matching
    )

    actual_duration = result['duration']
    expected_duration = segment['end_time'] - segment['start_time']

    print(f"    Generated: {actual_duration:.2f}s (expected: {expected_duration:.2f}s)")

    return {
        'segment_id': segment_id,
        'text': text,
        'start_time': segment['start_time'],
        'end_time': segment['end_time'],
        'expected_duration': expected_duration,
        'actual_duration': actual_duration,
        'audio_file': str(output_file.name),
    }


def concatenate_audio_segments(
    segments_metadata: List[Dict[str, Any]],
    demo_id: str,
    output_dir: Path,
    final_output_path: Path,
) -> Dict[str, Any]:
    """
    Concatenate audio segments with proper timing using pydub.

    Args:
        segments_metadata: List of segment metadata with timing info
        demo_id: Demo identifier
        output_dir: Directory containing segment files
        final_output_path: Path for final output file

    Returns:
        Dict with final audio metadata
    """
    try:
        from pydub import AudioSegment
    except ImportError:
        raise ImportError(
            "pydub is required for audio concatenation. Install with: pip install pydub"
        )

    print("\nConcatenating audio segments with timing...")

    # Start with empty audio
    final_audio = AudioSegment.empty()
    current_time = 0.0

    for segment_meta in segments_metadata:
        segment_id = segment_meta['segment_id']
        target_start_time = segment_meta['start_time']
        audio_file = output_dir / segment_meta['audio_file']

        # Add silence if there's a gap
        if target_start_time > current_time:
            gap_duration_ms = int((target_start_time - current_time) * 1000)
            silence = AudioSegment.silent(duration=gap_duration_ms)
            final_audio += silence
            print(f"  Added {gap_duration_ms}ms silence before segment {segment_id}")
            current_time = target_start_time

        # Load and add the audio segment
        segment_audio = AudioSegment.from_mp3(str(audio_file))
        final_audio += segment_audio

        segment_duration_sec = len(segment_audio) / 1000.0
        current_time += segment_duration_sec

        print(f"  Added segment {segment_id}: {segment_duration_sec:.2f}s @ {target_start_time:.2f}s")

    # Export final audio
    print(f"\nExporting final audio to: {final_output_path}")
    final_audio.export(
        str(final_output_path),
        format="mp3",
        bitrate="192k",
        parameters=["-q:a", "0"],  # Highest quality VBR (Variable Bit Rate)
    )

    final_duration = len(final_audio) / 1000.0

    return {
        'output_path': str(final_output_path),
        'duration_seconds': final_duration,
        'segment_count': len(segments_metadata),
        'format': 'mp3',
        'bitrate': '192k',
    }


def generate_demo_audio(demo_id: str) -> Dict[str, Any]:
    """
    Main function to generate complete demo narration audio.

    Args:
        demo_id: Demo identifier (e.g., "DEMO-knowledge-engine-pages")

    Returns:
        Dict with generation results and metadata
    """
    # Check API key
    if not check_api_key():
        raise ValueError(
            "ELEVENLABS_API_KEY environment variable not set. "
            "Get your API key from: https://elevenlabs.io/app/settings/api-keys"
        )

    voice_id = os.getenv("ELEVENLABS_VOICE_ID")
    if not voice_id:
        raise ValueError(
            "ELEVENLABS_VOICE_ID environment variable not set. "
            "Find voice IDs at: https://elevenlabs.io/app/voice-library"
        )

    print(f"=== Audio Generation for {demo_id} ===\n")
    print(f"Voice ID: {voice_id}")

    # Load narration data
    print("\nLoading narration data...")
    narration_data = load_narration(demo_id)
    segments = narration_data['narration_segments']
    total_duration = narration_data['total_duration_seconds']

    print(f"  Total segments: {len(segments)}")
    print(f"  Expected duration: {total_duration:.2f}s")

    # Create output directories
    demo_dir = Path(f".demo/{demo_id}")
    audio_segments_dir = demo_dir / "audio_segments"
    audio_segments_dir.mkdir(parents=True, exist_ok=True)

    # Initialize ElevenLabs client
    client = ElevenLabsClient()

    # Generate audio for each segment
    print("\nGenerating audio segments...")
    segments_metadata = []

    for segment in segments:
        try:
            metadata = generate_segment_audio(
                client=client,
                segment=segment,
                demo_id=demo_id,
                output_dir=audio_segments_dir,
            )
            segments_metadata.append(metadata)
        except Exception as e:
            print(f"  ERROR: Failed to generate segment {segment['segment_id']}: {e}")
            raise

    # Concatenate all segments
    final_output_path = demo_dir / "narration_audio.mp3"

    final_metadata = concatenate_audio_segments(
        segments_metadata=segments_metadata,
        demo_id=demo_id,
        output_dir=audio_segments_dir,
        final_output_path=final_output_path,
    )

    # Compare with expected duration
    actual_duration = final_metadata['duration_seconds']
    duration_diff = actual_duration - total_duration

    print(f"\n=== Generation Complete ===")
    print(f"  Output: {final_output_path}")
    print(f"  Duration: {actual_duration:.2f}s (expected: {total_duration:.2f}s)")
    print(f"  Difference: {duration_diff:+.2f}s")

    if abs(duration_diff) > 5.0:
        print(f"  WARNING: Duration differs by more than 5 seconds!")

    # Save metadata
    metadata_path = demo_dir / "audio_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump({
            'final_audio': final_metadata,
            'segments': segments_metadata,
            'expected_duration': total_duration,
            'voice_id': voice_id,
        }, f, indent=2)

    print(f"  Metadata saved to: {metadata_path}")

    return final_metadata


def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: python3 generate_audio.py <demo_id>")
        print("\nExample:")
        print("  python3 generate_audio.py DEMO-knowledge-engine-pages")
        sys.exit(1)

    demo_id = sys.argv[1]

    try:
        result = generate_demo_audio(demo_id)
        print(f"\nSuccess! Audio generated: {result['output_path']}")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
