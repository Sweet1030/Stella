import discord
from discord import app_commands
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
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")

@bot.command()
@commands.is_owner()
async def sync(ctx):
    """슬래시 커맨드를 수동으로 동기화합니다. (봇 소유자 전용)"""
    try:
        synced = await bot.tree.sync()
        await ctx.send(f"✅ {len(synced)}개의 슬래시 커맨드가 동기화되었습니다.")
    except Exception as e:
        await ctx.send(f"❌ 동기화 실패: {e}")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏳ 쿨타임 중입니다. {error.retry_after:.1f}초 후에 다시 시도해주세요.", ephemeral=True)
    elif isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("🚫 명령어를 실행할 권한이 없습니다.", ephemeral=True)
    else:
        print(f"App Command Error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ 오류가 발생했습니다: {error}", ephemeral=True)

async def load_cogs():
    await bot.load_extension("cogs.moderation")
    await bot.load_extension("cogs.gambling")
    await bot.load_extension("cogs.general")
    await bot.load_extension("cogs.upgrade")

def main():
    bot.run(config.DISCORD_TOKEN)

@bot.event
async def setup_hook():
    from services.db import init_db
    await init_db()
    await load_cogs()

if __name__ == "__main__":
    main()