import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
GOD_CHANNEL_NAME = os.getenv("GOD_CHANNEL_NAME") or None
BOT_COMMAND_PREFIX = os.getenv("BOT_COMMAND_PREFIX", "!")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemma-4-31b-it")
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemma-4-26b-a4b-it")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
ARCHITECT_TEMPERATURE = float(os.getenv("ARCHITECT_TEMPERATURE", "0.8"))
COUNCIL_TEMPERATURE = float(os.getenv("COUNCIL_TEMPERATURE", "0.8"))
TICK_INTERVAL_SECONDS = int(os.getenv("TICK_INTERVAL_SECONDS", "60"))
NOTIFY_USER_ID = os.getenv("NOTIFY_USER_ID", "769082859557355542")
