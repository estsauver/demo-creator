#!/usr/bin/env python3
"""
List available ElevenLabs voices.

This script helps you find the right voice ID for your demo narration.

Usage:
    export ELEVENLABS_API_KEY=your_api_key
    python3 list_voices.py
"""

import os
import sys
import requests
from typing import List, Dict, Any


def list_voices() -> List[Dict[str, Any]]:
    """
    Fetch available voices from ElevenLabs API.

    Returns:
        List of voice dictionaries with id, name, and metadata
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError(
            "ELEVENLABS_API_KEY environment variable not set.\n"
            "Get your API key from: https://elevenlabs.io/app/settings/api-keys"
        )

    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": api_key}

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()
    return data.get("voices", [])


def main():
    """CLI entry point"""
    try:
        print("Fetching available voices from ElevenLabs...\n")
        voices = list_voices()

        print(f"Found {len(voices)} voices:\n")
        print(f"{'Voice ID':<25} {'Name':<20} {'Category':<15} {'Description'}")
        print("=" * 100)

        # Recommended voices for professional narration
        recommended_ids = {
            "21m00Tcm4TlvDq8ikWAM",  # Rachel
            "ErXwobaYiN019PkySvjV",  # Antoni
            "TxGEqnHWrfWFTfGW9XjX",  # Josh
            "VR6AewLTigWG4xSOukaG",  # Arnold
        }

        for voice in voices:
            voice_id = voice["voice_id"]
            name = voice["name"]
            category = voice.get("category", "N/A")
            description = voice.get("description", "")[:50]

            # Highlight recommended voices
            marker = " ★" if voice_id in recommended_ids else ""

            print(f"{voice_id:<25} {name:<20} {category:<15} {description}{marker}")

        print("\n★ = Recommended for professional narration")
        print("\nPopular choices:")
        print("  • Rachel (21m00Tcm4TlvDq8ikWAM) - Professional female voice")
        print("  • Antoni (ErXwobaYiN019PkySvjV) - Calm, authoritative male voice")
        print("  • Josh (TxGEqnHWrfWFTfGW9XjX) - Clear, professional male voice")
        print("  • Arnold (VR6AewLTigWG4xSOukaG) - Deep, commanding male voice")

        print("\nTo use a voice, set the ELEVENLABS_VOICE_ID environment variable:")
        print("  export ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
