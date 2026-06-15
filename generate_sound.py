"""
Run this script once to generate the whistle MP3 used at end of half.
Requires: pydub + ffmpeg in PATH.

Usage:
    python generate_sound.py
"""

import os
from pydub import AudioSegment
from pydub.generators import Sine


def generate_whistle(output_path: str = "sounds/whistle.mp3"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Referee whistle: short high-pitched bursts around 2–3 kHz
    def burst(freq: int, ms: int, db: int = 8) -> AudioSegment:
        tone = Sine(freq).to_audio_segment(duration=ms)
        fade = tone.fade_in(30).fade_out(50)
        return fade + db  # boost

    silence = AudioSegment.silent(duration=120)

    # Three short blasts + one long ending blast
    whistle = (
        burst(2637, 300) + silence +
        burst(2637, 300) + silence +
        burst(2637, 300) + silence +
        burst(2349, 800)
    )

    # Normalise to max volume
    whistle = whistle.normalize()

    whistle.export(output_path, format="mp3", bitrate="128k")
    print(f"Whistle generated: {output_path}  ({len(whistle) / 1000:.1f}s)")


if __name__ == "__main__":
    generate_whistle()
