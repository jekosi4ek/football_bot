import io
import logging
import tempfile
import os

import speech_recognition as sr
from pydub import AudioSegment

from config import SPEECH_LANGUAGE

logger = logging.getLogger(__name__)


async def download_voice(bot, file_id: str) -> bytes:
    """Download a Telegram voice file and return raw bytes."""
    tg_file = await bot.get_file(file_id)
    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    buf.seek(0)
    return buf.read()


def ogg_to_wav(ogg_bytes: bytes) -> bytes:
    """Convert OGG/OPUS bytes (Telegram voice) to PCM WAV bytes."""
    ogg_buf = io.BytesIO(ogg_bytes)
    audio = AudioSegment.from_ogg(ogg_buf)
    wav_buf = io.BytesIO()
    audio.export(wav_buf, format="wav")
    wav_buf.seek(0)
    return wav_buf.read()


def transcribe_wav(wav_bytes: bytes, language: str = SPEECH_LANGUAGE) -> str | None:
    """Transcribe WAV audio bytes using Google Speech Recognition (free tier)."""
    recognizer = sr.Recognizer()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(wav_bytes)
        tmp_path = tmp.name

    try:
        with sr.AudioFile(tmp_path) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language=language)
        logger.info("Transcribed: %s", text)
        return text
    except sr.UnknownValueError:
        logger.warning("Google Speech Recognition could not understand audio")
        return None
    except sr.RequestError as e:
        logger.error("Google Speech Recognition error: %s", e)
        return None
    finally:
        os.unlink(tmp_path)


def extract_player_name(text: str) -> str | None:
    """
    Heuristic extraction of a player name from transcribed voice text.

    Handles phrases like:
      "додай Іванця"  /  "гравець Петро"  /  "запиши Олег Марченко"
      or simply a plain name with no trigger word.
    """
    if not text:
        return None

    text = text.strip()
    triggers = [
        "додай", "додати", "гравець", "гравця", "запиши", "запишіть",
        "зареєструй", "реєструй", "add", "player",
    ]

    lower = text.lower()
    for trigger in triggers:
        idx = lower.find(trigger)
        if idx != -1:
            after = text[idx + len(trigger):].strip()
            if after:
                # Take at most the first two words as the name
                parts = after.split()
                name = " ".join(parts[:2]).strip(".,!?")
                return name.title() if name else None

    # No trigger found — treat entire text as the name (capitalised)
    parts = text.split()
    name = " ".join(parts[:2]).strip(".,!?")
    return name.title() if name else None


async def process_voice_raw(bot, file_id: str) -> str | None:
    """Download → convert → transcribe. Returns raw transcribed text or None."""
    try:
        ogg_bytes = await download_voice(bot, file_id)
        wav_bytes = ogg_to_wav(ogg_bytes)
        return transcribe_wav(wav_bytes)
    except Exception as e:
        logger.error("Voice processing failed: %s", e)
        return None


async def process_voice_message(bot, file_id: str) -> str | None:
    """Full pipeline: download → convert → transcribe → extract name."""
    text = await process_voice_raw(bot, file_id)
    return extract_player_name(text)
