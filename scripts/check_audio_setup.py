#!/usr/bin/env python3
"""
Check if audio generation environment is properly configured.

This script verifies:
- ElevenLabs API key is set
- Voice ID is configured
- Required dependencies are installed
- ffmpeg is available

Usage:
    python3 check_audio_setup.py
"""

import os
import sys
import subprocess
from pathlib import Path


def check_env_var(name: str, required: bool = True) -> bool:
    """Check if an environment variable is set."""
    value = os.getenv(name)
    if value:
        masked = value[:8] + "..." if len(value) > 8 else value
        print(f"  ✓ {name}: {masked}")
        return True
    else:
        symbol = "✗" if required else "○"
        status = "REQUIRED" if required else "optional"
        print(f"  {symbol} {name}: Not set ({status})")
        return not required


def check_python_package(package_name: str, import_name: str = None) -> bool:
    """Check if a Python package is installed."""
    if import_name is None:
        import_name = package_name

    try:
        __import__(import_name)
        print(f"  ✓ {package_name}: Installed")
        return True
    except ImportError:
        print(f"  ✗ {package_name}: Not installed")
        return False


def check_command(command: str) -> bool:
    """Check if a system command is available."""
    try:
        result = subprocess.run(
            [command, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Get version from output
            version = result.stdout.split('\n')[0] if result.stdout else "unknown"
            print(f"  ✓ {command}: {version}")
            return True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    print(f"  ✗ {command}: Not found")
    return False


def main():
    """Run all checks."""
    print("=== Audio Generation Environment Check ===\n")

    all_ok = True

    # Check environment variables
    print("Environment Variables:")
    all_ok &= check_env_var("ELEVENLABS_API_KEY", required=True)
    all_ok &= check_env_var("ELEVENLABS_VOICE_ID", required=True)
    print()

    # Check Python packages
    print("Python Dependencies:")
    all_ok &= check_python_package("pydub")
    all_ok &= check_python_package("requests")
    print()

    # Check system commands
    print("System Dependencies:")
    all_ok &= check_command("ffmpeg")
    print()

    # Check demo files
    print("Demo Files:")
    demo_id = "DEMO-knowledge-engine-pages"
    narration_file = Path(f".demo/{demo_id}/narration.json")

    if narration_file.exists():
        print(f"  ✓ Narration file: {narration_file}")
    else:
        print(f"  ✗ Narration file not found: {narration_file}")
        all_ok = False
    print()

    # Summary
    print("=" * 50)
    if all_ok:
        print("✓ All checks passed! Ready to generate audio.")
        print("\nRun:")
        print(f"  python3 plugins/demo-creator/generate_audio.py {demo_id}")
        return 0
    else:
        print("✗ Some checks failed. Please fix the issues above.")
        print("\nSetup instructions:")
        print("  1. Get ElevenLabs API key: https://elevenlabs.io/app/settings/api-keys")
        print("  2. Choose a voice: python3 plugins/demo-creator/list_voices.py")
        print("  3. Install dependencies: pip install pydub requests")
        print("  4. Install ffmpeg: brew install ffmpeg (macOS)")
        print("\nThen set environment variables:")
        print("  export ELEVENLABS_API_KEY=your_api_key")
        print("  export ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM")
        return 1


if __name__ == "__main__":
    sys.exit(main())
