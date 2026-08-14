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
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:0.5b")
TICK_INTERVAL_SECONDS = int(os.getenv("TICK_INTERVAL_SECONDS", "60"))
