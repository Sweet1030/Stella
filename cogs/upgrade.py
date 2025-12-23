from discord.ext import commands
import discord
from discord import app_commands
import random
from services.upgrade_service import UpgradeService


class MinigameView(discord.ui.View):
    """1~5 숫자 맞추기 미니게임"""
    def __init__(self, user_id: int, callback):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.callback = callback
        self.correct_number = random.randint(1, 5)
        self.bonus = 0.0
        self.answered = False
        
        # 1~5 버튼 생성
        for i in range(1, 6):
            button = discord.ui.Button(
                label=str(i),
                style=discord.ButtonStyle.secondary,
                custom_id=f"minigame_{i}"
            )
            button.callback = self.create_callback(i)
            self.add_item(button)
    
    def create_callback(self, number: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("자신의 게임만 조작할 수 있습니다.", ephemeral=True)
                return
            
            if self.answered:
                await interaction.response.send_message("이미 선택했습니다.", ephemeral=True)
                return
            
            self.answered = True
            
            if number == self.correct_number:
                self.bonus = 0.03  # +3% 보너스
                embed = discord.Embed(
                    title="🎯 정답!",
                    description=f"숫자 **{number}**을(를) 맞췄습니다!\n성공 확률 **+3%** 보너스가 적용됩니다.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ 오답",
                    description=f"정답은 **{self.correct_number}**이었습니다.\n보너스 없이 강화를 진행합니다.",
                    color=discord.Color.red()
                )
            
            self.stop()
            await interaction.response.edit_message(embed=embed, view=None)
            await self.callback(interaction, self.bonus)
        
        return callback

    async def on_timeout(self):
        self.stop()


class UpgradeConfirmView(discord.ui.View):
    """강화 확인 뷰"""
    def __init__(self, user_id: int, upgrade_service: UpgradeService, level: int, balance: int, minigame_bonus: float = 0.0):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.upgrade_service = upgrade_service
        self.level = level
        self.balance = balance
        self.minigame_bonus = minigame_bonus
        self.cost = upgrade_service.calculate_cost(level)
        self.rate = upgrade_service.calculate_success_rate(level, minigame_bonus)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("자신의 강화만 진행할 수 있습니다.", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="🔨 강화하기", style=discord.ButtonStyle.danger)
    async def do_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        result = await self.upgrade_service.upgrade(self.user_id, self.minigame_bonus)
        
        if result.get("error") == "insufficient_balance":
            await interaction.response.edit_message(
                content="❌ 잔액이 부족합니다!",
                embed=None,
                view=None
            )
            return
        
        if result.get("error") == "max_level":
            await interaction.response.edit_message(
                content="🏆 이미 최대 레벨(100)입니다!",
                embed=None,
                view=None
            )
            return
        
        tier_name = self.upgrade_service.get_tier_name(result["new_level"])
        tier_emoji = self.upgrade_service.TIER_EMOJIS.get(tier_name, "⚪")
        tier_color = self.upgrade_service.TIER_COLORS.get(tier_name, 0x808080)
        
        if result["destroyed"]:
            embed = discord.Embed(
                title="💥 장비 파괴!",
                description=f"강화에 실패하여 장비가 파괴되었습니다...\n\n"
                           f"**Lv. {result['old_level']}** → **Lv. 1**",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="소모 비용", value=f"{result['cost']:,}원", inline=True)
        elif result["success"]:
            embed = discord.Embed(
                title="✨ 강화 성공!",
                description=f"{tier_emoji} **Lv. {result['old_level']}** → **Lv. {result['new_level']}** (+{result['change']})",
                color=tier_color
            )
            embed.add_field(name="소모 비용", value=f"{result['cost']:,}원", inline=True)
            embed.add_field(name="현재 등급", value=tier_name, inline=True)
            if result["new_record"]:
                embed.set_footer(text="🎉 신기록 달성!")
        else:
            if result["change"] < 0:
                desc = f"강화에 실패하여 레벨이 하락했습니다.\n\n**Lv. {result['old_level']}** → **Lv. {result['new_level']}** ({result['change']})"
            else:
                desc = f"강화에 실패했지만 레벨이 유지되었습니다.\n\n**Lv. {result['old_level']}** (유지)"
            embed = discord.Embed(
                title="❌ 강화 실패",
                description=desc,
                color=discord.Color.orange()
            )
            embed.add_field(name="소모 비용", value=f"{result['cost']:,}원", inline=True)
        
        # 다시 강화 버튼 제공
        new_level, _ = await self.upgrade_service.get_user_gear(self.user_id)
        new_balance = await self.upgrade_service.get_balance(self.user_id)
        
        view = UpgradeMainView(self.user_id, self.upgrade_service, new_level, new_balance)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="🎯 미니게임 (확률+3%)", style=discord.ButtonStyle.primary)
    async def play_minigame(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎯 숫자 맞추기 미니게임",
            description="1~5 중 하나를 선택하세요!\n정답을 맞추면 성공 확률 **+3%** 보너스!",
            color=discord.Color.blue()
        )
        
        async def after_minigame(minigame_interaction: discord.Interaction, bonus: float):
            # 미니게임 후 강화 진행
            result = await self.upgrade_service.upgrade(self.user_id, bonus)
            
            if result.get("error") == "insufficient_balance":
                await minigame_interaction.followup.send("❌ 잔액이 부족합니다!", ephemeral=True)
                return
            
            tier_name = self.upgrade_service.get_tier_name(result["new_level"])
            tier_emoji = self.upgrade_service.TIER_EMOJIS.get(tier_name, "⚪")
            tier_color = self.upgrade_service.TIER_COLORS.get(tier_name, 0x808080)
            
            bonus_text = "(+3% 보너스 적용)" if bonus > 0 else "(보너스 없음)"
            
            if result["destroyed"]:
                embed = discord.Embed(
                    title="💥 장비 파괴!",
                    description=f"강화에 실패하여 장비가 파괴되었습니다... {bonus_text}\n\n"
                               f"**Lv. {result['old_level']}** → **Lv. 1**",
                    color=discord.Color.dark_red()
                )
            elif result["success"]:
                embed = discord.Embed(
                    title="✨ 강화 성공!",
                    description=f"{tier_emoji} **Lv. {result['old_level']}** → **Lv. {result['new_level']}** (+{result['change']}) {bonus_text}",
                    color=tier_color
                )
                if result["new_record"]:
                    embed.set_footer(text="🎉 신기록 달성!")
            else:
                if result["change"] < 0:
                    desc = f"강화에 실패하여 레벨이 하락했습니다. {bonus_text}\n\n**Lv. {result['old_level']}** → **Lv. {result['new_level']}** ({result['change']})"
                else:
                    desc = f"강화에 실패했지만 레벨이 유지되었습니다. {bonus_text}\n\n**Lv. {result['old_level']}** (유지)"
                embed = discord.Embed(
                    title="❌ 강화 실패",
                    description=desc,
                    color=discord.Color.orange()
                )
            
            embed.add_field(name="소모 비용", value=f"{result['cost']:,}원", inline=True)
            
            new_level, _ = await self.upgrade_service.get_user_gear(self.user_id)
            new_balance = await self.upgrade_service.get_balance(self.user_id)
            view = UpgradeMainView(self.user_id, self.upgrade_service, new_level, new_balance)
            await minigame_interaction.followup.send(embed=embed, view=view)
        
        view = MinigameView(self.user_id, after_minigame)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="강화를 취소했습니다.", embed=None, view=None)


class UpgradeMainView(discord.ui.View):
    """메인 강화 UI"""
    def __init__(self, user_id: int, upgrade_service: UpgradeService, level: int, balance: int):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.upgrade_service = upgrade_service
        self.level = level
        self.balance = balance
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("자신의 강화만 진행할 수 있습니다.", ephemeral=True)
            return False
        return True
    
    def get_embed(self) -> discord.Embed:
        tier_name = self.upgrade_service.get_tier_name(self.level)
        tier_emoji = self.upgrade_service.TIER_EMOJIS.get(tier_name, "⚪")
        tier_color = self.upgrade_service.TIER_COLORS.get(tier_name, 0x808080)
        cost = self.upgrade_service.calculate_cost(self.level)
        rate = self.upgrade_service.calculate_success_rate(self.level)
        tier_info = self.upgrade_service.get_tier_info(self.level)
        
        embed = discord.Embed(
            title="🔨 장비 강화",
            color=tier_color
        )
        embed.add_field(name="현재 레벨", value=f"{tier_emoji} **Lv. {self.level}** ({tier_name})", inline=False)
        embed.add_field(name="강화 비용", value=f"{cost:,}원", inline=True)
        embed.add_field(name="성공 확률", value=f"{rate*100:.1f}%", inline=True)
        embed.add_field(name="보유 잔액", value=f"{self.balance:,}원", inline=True)
        
        # 등급별 추가 정보
        if tier_info["destroy"] > 0:
            embed.add_field(name="⚠️ 파괴 확률", value=f"{tier_info['destroy']*100:.0f}%", inline=True)
        
        if self.level >= 100:
            embed.set_footer(text="🏆 최대 레벨에 도달했습니다!")
        elif self.balance < cost:
            embed.set_footer(text="❌ 잔액이 부족합니다")
        else:
            embed.set_footer(text="💡 미니게임에 성공하면 +3% 보너스!")
        
        return embed
    
    @discord.ui.button(label="🔨 강화 진행", style=discord.ButtonStyle.success)
    async def start_upgrade(self, interaction: discord.Interaction, button: discord.ui.Button):
        cost = self.upgrade_service.calculate_cost(self.level)
        
        if self.balance < cost:
            await interaction.response.send_message("❌ 잔액이 부족합니다!", ephemeral=True)
            return
        
        if self.level >= 100:
            await interaction.response.send_message("🏆 이미 최대 레벨입니다!", ephemeral=True)
            return
        
        rate = self.upgrade_service.calculate_success_rate(self.level)
        tier_info = self.upgrade_service.get_tier_info(self.level)
        
        embed = discord.Embed(
            title="⚠️ 강화 확인",
            description=f"**Lv. {self.level}** 강화를 진행하시겠습니까?",
            color=discord.Color.yellow()
        )
        embed.add_field(name="비용", value=f"{cost:,}원", inline=True)
        embed.add_field(name="성공 확률", value=f"{rate*100:.1f}%", inline=True)
        if tier_info["destroy"] > 0:
            embed.add_field(name="⚠️ 파괴 확률", value=f"{tier_info['destroy']*100:.0f}%", inline=True)
        
        view = UpgradeConfirmView(self.user_id, self.upgrade_service, self.level, self.balance)
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="🔄 새로고침", style=discord.ButtonStyle.secondary)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.level, _ = await self.upgrade_service.get_user_gear(self.user_id)
        self.balance = await self.upgrade_service.get_balance(self.user_id)
        await interaction.response.edit_message(embed=self.get_embed(), view=self)


class Upgrade(commands.Cog):
    """장비 강화 시스템"""
    def __init__(self, bot):
        self.bot = bot
        self.upgrade_service = UpgradeService.get_instance()
    
    upgrade_group = app_commands.Group(name="강화", description="장비 강화 관련 명령어")
    
    @upgrade_group.command(name="시작", description="장비 강화를 시작합니다.")
    async def start(self, interaction: discord.Interaction):
        level, max_level = await self.upgrade_service.get_user_gear(interaction.user.id)
        balance = await self.upgrade_service.get_balance(interaction.user.id)
        
        view = UpgradeMainView(interaction.user.id, self.upgrade_service, level, balance)
        await interaction.response.send_message(embed=view.get_embed(), view=view)
    
    @upgrade_group.command(name="정보", description="현재 장비 정보를 확인합니다.")
    async def info(self, interaction: discord.Interaction):
        level, max_level = await self.upgrade_service.get_user_gear(interaction.user.id)
        balance = await self.upgrade_service.get_balance(interaction.user.id)
        
        tier_name = self.upgrade_service.get_tier_name(level)
        tier_emoji = self.upgrade_service.TIER_EMOJIS.get(tier_name, "⚪")
        tier_color = self.upgrade_service.TIER_COLORS.get(tier_name, 0x808080)
        cost = self.upgrade_service.calculate_cost(level)
        rate = self.upgrade_service.calculate_success_rate(level)
        
        embed = discord.Embed(
            title="📊 장비 정보",
            color=tier_color
        )
        embed.add_field(name="현재 레벨", value=f"{tier_emoji} **Lv. {level}**", inline=True)
        embed.add_field(name="최고 기록", value=f"**Lv. {max_level}**", inline=True)
        embed.add_field(name="현재 등급", value=tier_name, inline=True)
        embed.add_field(name="다음 강화 비용", value=f"{cost:,}원", inline=True)
        embed.add_field(name="성공 확률", value=f"{rate*100:.1f}%", inline=True)
        embed.add_field(name="보유 잔액", value=f"{balance:,}원", inline=True)
        
        await interaction.response.send_message(embed=embed)
    
    @upgrade_group.command(name="랭킹", description="장비 레벨 랭킹을 확인합니다.")
    async def leaderboard(self, interaction: discord.Interaction):
        rankings = await self.upgrade_service.get_leaderboard()
        
        embed = discord.Embed(
            title="🏆 장비 강화 랭킹 TOP 10",
            color=discord.Color.gold()
        )
        
        if not rankings:
            embed.description = "아직 랭킹 데이터가 없습니다."
        else:
            for idx, (uid, gear_lv, max_lv) in enumerate(rankings, 1):
                try:
                    user = await self.bot.fetch_user(int(uid))
                    name = user.name
                except Exception:
                    name = "Unknown"
                
                tier_name = self.upgrade_service.get_tier_name(gear_lv or 1)
                tier_emoji = self.upgrade_service.TIER_EMOJIS.get(tier_name, "⚪")
                
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
                embed.add_field(
                    name=f"{medal} {name}",
                    value=f"{tier_emoji} Lv. {gear_lv} (최고: {max_lv})",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed)
    
    @upgrade_group.command(name="도움말", description="강화 시스템에 대한 도움말을 확인합니다.")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 장비 강화 시스템 도움말",
            description="장비를 강화하여 레벨을 올려보세요!",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎮 기본 규칙",
            value="• 레벨 범위: **Lv. 1 ~ 100**\n"
                  "• 강화 성공 시: **+1 ~ +3** 레벨 상승\n"
                  "• 강화 실패 시: 레벨 유지, 하락, 또는 파괴",
            inline=False
        )
        
        embed.add_field(
            name="⚪ Rookie (1~20)",
            value="성공률 85~100% | 실패 시 유지",
            inline=True
        )
        embed.add_field(
            name="🟢 Common (21~40)",
            value="성공률 60~80% | 실패 시 유지 or -1",
            inline=True
        )
        embed.add_field(
            name="🔵 Rare (41~60)",
            value="성공률 35~55% | 실패 시 -1~3",
            inline=True
        )
        embed.add_field(
            name="🟣 Epic (61~70)",
            value="성공률 20~30% | 파괴 1%",
            inline=True
        )
        embed.add_field(
            name="🟡 Legendary (71~80)",
            value="성공률 12~18% | 파괴 3%",
            inline=True
        )
        embed.add_field(
            name="🔴 Mythic (81~90)",
            value="성공률 5~10% | 파괴 7%",
            inline=True
        )
        embed.add_field(
            name="💎 Ascension (91~100)",
            value="성공률 1~3% | **실패 시 파괴**",
            inline=True
        )
        
        embed.add_field(
            name="🎯 미니게임",
            value="강화 전 1~5 숫자 맞추기에 성공하면 **+3%** 보너스 확률!",
            inline=False
        )
        
        embed.set_footer(text="💡 /강화 시작 명령어로 강화를 시작하세요!")
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Upgrade(bot))
