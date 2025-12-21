from discord.ext import commands
from discord import app_commands
import discord

MAX_CLEAR = 50

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="삭제", description="채팅을 삭제합니다. (최대 50개)")
    @app_commands.describe(amount="삭제할 메시지 수")
    async def clear(self, interaction: discord.Interaction, amount: int = 5):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message(
                "❌ 메시지 관리 권한이 없습니다.",
                ephemeral=True
            )
            return

        if amount > MAX_CLEAR:
            await interaction.response.send_message(
                f"❌ 최대 {MAX_CLEAR}개까지만 삭제할 수 있습니다.",
                ephemeral=True
            )
            return

        deleted = await interaction.channel.purge(limit=amount)
        await interaction.response.send_message(
            f"🧹 {len(deleted)}개의 메시지를 삭제했습니다.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Moderation(bot))
