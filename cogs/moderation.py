from discord.ext import commands
from discord import app_commands
import discord
import datetime
from services.moderation_service import ModerationService

MAX_CLEAR = 50

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = ModerationService.get_instance()

    @app_commands.command(name="삭제", description="채팅을 삭제합니다. (최대 50개)")
    @app_commands.describe(amount="삭제할 메시지 수")
    async def clear(self, interaction: discord.Interaction, amount: int = 5):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ 메시지 관리 권한이 없습니다.", ephemeral=True)
            return

        if amount > MAX_CLEAR:
            await interaction.response.send_message(f"❌ 최대 {MAX_CLEAR}개까지만 삭제할 수 있습니다.", ephemeral=True)
            return

        deleted = await interaction.channel.purge(limit=amount)
        await interaction.response.send_message(f"🧹 {len(deleted)}개의 메시지를 삭제했습니다.", ephemeral=True)

    @app_commands.command(name="타임아웃", description="유저를 일정 시간 동안 타임아웃 처리합니다.")
    @app_commands.describe(member="대상 유저", minutes="시간 (분)", reason="사유")
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "사유 없음"):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ 유저 관리 권한이 없습니다.", ephemeral=True)
            return

        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"🔇 {member.mention}님을 {minutes}분 동안 타임아웃 처리했습니다. (사유: {reason})")

    @app_commands.command(name="추방", description="유저를 서버에서 추방합니다.")
    @app_commands.describe(member="대상 유저", reason="사유")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "사유 없음"):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ 추방 권한이 없습니다.", ephemeral=True)
            return

        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 {member.mention}님을 추방했습니다. (사유: {reason})")

    @app_commands.command(name="차단", description="유저를 서버에서 차단합니다.")
    @app_commands.describe(member="대상 유저", delete_days="메시지 삭제 기간 (일)", reason="사유")
    async def ban(self, interaction: discord.Interaction, member: discord.Member, delete_days: int = 0, reason: str = "사유 없음"):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ 차단 권한이 없습니다.", ephemeral=True)
            return

        await member.ban(delete_message_days=delete_days, reason=reason)
        await interaction.response.send_message(f"🔨 {member.mention}님을 차단했습니다. (사유: {reason})")

    @app_commands.command(name="유저정보", description="유저의 상세 정보를 확인합니다.")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles_str = ", ".join(roles) if roles else "없음"
        
        embed = discord.Embed(title=f"👤 {member.name} 님의 정보", color=member.color)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="가입일", value=member.joined_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="계정 생성일", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="역할", value=roles_str, inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="슬로우모드", description="채널의 슬로우모드를 설정합니다.")
    @app_commands.describe(seconds="초 (0으로 설정 시 해제)")
    async def slowmode(self, interaction: discord.Interaction, seconds: int):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ 채널 관리 권한이 없습니다.", ephemeral=True)
            return

        await interaction.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await interaction.response.send_message("🐢 슬로우모드가 해제되었습니다.")
        else:
            await interaction.response.send_message(f"🐢 슬로우모드가 {seconds}초로 설정되었습니다.")

    @app_commands.command(name="경고", description="유저에게 경고를 부여합니다.")
    @app_commands.describe(member="대상 유저", reason="사유")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ 유저 관리 권한이 없습니다.", ephemeral=True)
            return

        count = await self.service.add_warning(member.id, reason, interaction.user.id)
        
        # DM 발송
        try:
            embed = discord.Embed(title="⚠️ 경고 알림", color=discord.Color.red())
            embed.add_field(name="서버", value=interaction.guild.name, inline=False)
            embed.add_field(name="사유", value=reason, inline=False)
            embed.add_field(name="누적 경고", value=f"{count}회", inline=False)
            embed.set_footer(text=f"처리자: {interaction.user.name}")
            await member.send(embed=embed)
            dm_status = "DM 발송 성공"
        except discord.Forbidden:
            dm_status = "DM 발송 실패 (유저가 DM을 막아둠)"
        except Exception:
            dm_status = "DM 발송 실패 (알 수 없는 오류)"

        await interaction.response.send_message(f"⚠️ {member.mention}님에게 경고를 부여했습니다. (누적 {count}회)\n사유: {reason}\n({dm_status})")

    @app_commands.command(name="경고목록", description="유저의 경고 목록을 확인합니다.")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ 유저 관리 권한이 없습니다.", ephemeral=True)
            return

        warnings = await self.service.get_warnings(member.id)
        if not warnings:
            await interaction.response.send_message(f"✅ {member.mention}님은 경고 기록이 없습니다.")
            return

        embed = discord.Embed(title=f"⚠️ {member.name}님의 경고 기록", color=discord.Color.orange())
        for idx, warn in enumerate(warnings, 1):
            moderator = interaction.guild.get_member(warn['moderator_id'])
            mod_name = moderator.name if moderator else "Unknown"
            embed.add_field(name=f"{idx}. {warn['date']}", value=f"사유: {warn['reason']}\n처리자: {mod_name}", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="경고초기화", description="유저의 모든 경고를 초기화합니다.")
    async def clear_warnings(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)
            return

        await self.service.clear_warnings(member.id)
        await interaction.response.send_message(f"♻️ {member.mention}님의 모든 경고를 초기화했습니다.")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
