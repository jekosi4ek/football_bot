import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
DATABASE_PATH = os.getenv("DATABASE_PATH", "football.db")
DEFAULT_HALF_DURATION = int(os.getenv("DEFAULT_HALF_DURATION", "7"))
SPEECH_LANGUAGE = os.getenv("SPEECH_LANGUAGE", "uk-UA")
WHISTLE_SOUND_PATH = os.path.join(os.path.dirname(__file__), "sounds", "whistle.mp3")

# Timer update interval (seconds) — Telegram allows ~20 edits/min per message
TIMER_UPDATE_INTERVAL = 5
