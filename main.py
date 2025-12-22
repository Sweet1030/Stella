import discord
from discord.ext import commands
import config

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

@bot.event
async def on_ready():
    print(f"{bot.user}")

    try:
        synced = await bot.tree.sync()
        print(f"슬래시 커맨드 {len(synced)}개가 동기화 되었습니다.")
    except Exception as e:
        print(f"슬래시 커맨드 동기화 실패: {e}")

async def load_cogs():
    await bot.load_extension("cogs.moderation")
    await bot.load_extension("cogs.game")
    await bot.load_extension("cogs.general")

def main():
    bot.run(config.DISCORD_TOKEN)

@bot.event
async def setup_hook():
    from services.db import init_db
    await init_db()
    await load_cogs()

if __name__ == "__main__":
    main()