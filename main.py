# main.py
import os, asyncio, signal
import discord
from discord.ext import commands
import aiohttp

from db import Database
import webserver

COGS = [
    "cogs.tickets",
    "cogs.verification",
    "cogs.points",
    "cogs.audit_log",
    "cogs.persistent_panels",
    "cogs.bot_speak",
]

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise SystemExit("DISCORD_BOT_TOKEN not set")

intents = discord.Intents.default()
intents.message_content = True  # enable only if you actually need it
bot = commands.Bot(command_prefix="!", intents=intents)
db = Database()

async def start_bot():
    # init DB
    await db.init()
    bot.db = db

    # shared http session
    bot.http = aiohttp.ClientSession()
    # load cogs
    for cog in COGS:
        try:
            bot.load_extension(cog)
            print(f"Loaded {cog}")
        except Exception as e:
            print(f"Failed to load {cog}: {e}")

    # start webserver (healthcheck)
    webserver.start()

    # run bot
    await bot.start(TOKEN)

async def shutdown():
    print("Shutting down...")
    try:
        await bot.close()
    except Exception:
        pass
    try:
        if hasattr(bot, "http"):
            await bot.http.close()
    except Exception:
        pass
    await db.close()
    await asyncio.sleep(0.1)

def run():
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    try:
        loop.run_until_complete(start_bot())
    except KeyboardInterrupt:
        loop.run_until_complete(shutdown())
    except Exception as e:
        print("Bot crashed:", e)
        loop.run_until_complete(shutdown())

if __name__ == "__main__":
    run()
