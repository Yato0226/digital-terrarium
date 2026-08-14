import state
from bot import bot as discord_bot
from config import DISCORD_BOT_TOKEN

if __name__ == "__main__":
    print("🌿 Digital Terrarium starting...")
    state.load_state()
    try:
        discord_bot.run(DISCORD_BOT_TOKEN)
    except KeyboardInterrupt:
        print("\n👋 Terrarium stopped gracefully.")
    finally:
        state.save_state()
