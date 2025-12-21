from discord.ext import commands
import discord
from discord import app_commands
import random
from services.economy import EconomyService

class CustomInputModal(discord.ui.Modal, title="도박 설정 직접 입력"):
    amount = discord.ui.TextInput(label="배팅 금액", placeholder="예: 5000 (숫자만 입력)", min_length=1)
    # multiplier = discord.ui.TextInput(label="배율 (Multiplier)", placeholder="예: 2.0 (1.1 ~ 10.0)", min_length=1) 
    # Let's ask for Win Probability or Multiplier. User asked for "multiplier adjustment".
    multiplier = discord.ui.TextInput(label="목표 배율", placeholder="예: 2.0 (최소 1.05)", min_length=1)

    def __init__(self, view):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amt = int(self.amount.value)
            mult = float(self.multiplier.value)
        except ValueError:
            await interaction.response.send_message("❌ 올바른 숫자를 입력해주세요.", ephemeral=True)
            return

        if amt < 100:
            await interaction.response.send_message("❌ 최소 배팅 금액은 100원입니다.", ephemeral=True)
            return
        
        # Max check handled in start
        
        if mult < 1.05:
            await interaction.response.send_message("❌ 배율은 최소 1.05배 이상이어야 합니다.", ephemeral=True)
            return

        # Calculate probability from multiplier
        # Multiplier = 0.99 / Probability  => Probability = 0.99 / Multiplier
        prob = 0.99 / mult
        
        if prob > 0.95: 
             prob = 0.95 # Cap max win chance
             # Recalc mult? No, keeping their mult means house edge changes. 
             # Let's stick to the formula: if mult is low, prob is high.
        
        if prob < 0.01:
            await interaction.response.send_message("❌ 배율이 너무 높습니다 (확률 1% 미만 불가).", ephemeral=True)
            return

        self.view.amount = amt
        self.view.probability = prob
        self.view.update_embed_data()
        await interaction.response.edit_message(embed=self.view.get_embed(), view=self.view)

class GambleView(discord.ui.View):
    def __init__(self, user_id, economy: EconomyService, amount, probability):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.economy = economy
        self.bet_amount = amount
        self.probability = probability
        self.multiplier = round(0.99 / probability, 2)
        self.current_pot = amount
        self.game_over = False
        self.started = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("자신의 게임만 조작할 수 있습니다.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        # Auto-claim if game started and pot > 0 and not game over
        if self.started and not self.game_over and self.current_pot > 0:
            self.economy.add_balance(self.user_id, self.current_pot)
            # Cannot reply to interaction easily on timeout without storing it, 
            # but the money is safe.
            # print(f"Auto-claimed {self.current_pot} for {self.user_id} due to timeout")

    @discord.ui.button(label="🎲 게임 시작", style=discord.ButtonStyle.green)
    async def start_game(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.clear_items() # Remove Start button
        self.started = True
        
        # Deduct initial bet
        if not self.economy.remove_balance(self.user_id, self.bet_amount):
            await interaction.response.edit_message(content="잔액이 부족합니다!", view=None, embed=None)
            self.stop()
            return

        await self.run_round(interaction)

    async def run_round(self, interaction: discord.Interaction):
        # Roll Logic
        roll = random.random()
        success = roll < self.probability
        
        notifications = self.economy.record_game_result(self.user_id, success, self.probability)
        
        embed = discord.Embed(title="🎲 도박 결과", color=discord.Color.gold() if success else discord.Color.red())
        note_text = "\n".join(notifications) if notifications else ""
        
        if success:
            self.current_pot = int(self.current_pot * self.multiplier)
            embed.description = f"**성공!** 🎉\n\n현재 누적 금액: **{self.current_pot:,}원**\n(배율: {self.multiplier}x / 확률: {int(self.probability*100)}%)\n\n{note_text}"
            
            # Update View with Continue/Stop
            self.clear_items()
            
            continue_btn = discord.ui.Button(label="계속", style=discord.ButtonStyle.primary)
            continue_btn.callback = self.continue_game
            self.add_item(continue_btn)
            
            stop_btn = discord.ui.Button(label="중단 (보상 수령)", style=discord.ButtonStyle.secondary)
            stop_btn.callback = self.stop_game
            self.add_item(stop_btn)
            
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
        else:
            self.current_pot = 0
            self.game_over = True
            embed.description = f"**실패...** 💥\n돈을 모두 잃었습니다.\n\n{note_text}"
            self.stop()
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=None)
            else:
                await interaction.response.edit_message(embed=embed, view=None)
            
            # Trigger Random Quest Chance (5%)
            if random.random() < 0.05:
                await self.trigger_random_quest(interaction)

    async def continue_game(self, interaction: discord.Interaction):
        await self.run_round(interaction)

    async def stop_game(self, interaction: discord.Interaction):
        self.game_over = True
        self.economy.add_balance(self.user_id, self.current_pot)
        embed = discord.Embed(title="💰 게임 종료", description=f"**{self.current_pot:,}원**을 획득했습니다!", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def trigger_random_quest(self, interaction: discord.Interaction):
        quest = self.economy.assign_quest(self.user_id)
        if not quest:
            return

        embed = discord.Embed(title="📜 돌발 퀘스트 발생!", description=f"**{quest['target']}연승 도전**\n성공 시: +{quest['reward']:,}원\n실패 시: -{quest['penalty']:,}원\n\n수락하시겠습니까?", color=discord.Color.purple())
        
        view = QuestView(self.user_id, self.economy)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class QuestView(discord.ui.View):
    def __init__(self, user_id, economy):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.economy = economy

    @discord.ui.button(label="수락", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="퀘스트를 수락했습니다! 다음 도박부터 적용됩니다.", view=None, embed=None)

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Remove the quest
        data = self.economy.get_user_data(self.user_id)
        data["active_quest"] = None
        self.economy._save_data()
        await interaction.response.edit_message(content="퀘스트를 거절했습니다.", view=None, embed=None)


class SettingsView(discord.ui.View):
    def __init__(self, user_id, economy, start_callback):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.economy = economy
        self.start_callback = start_callback
        self.amount = 1000
        self.probability = 0.5
        self.update_embed_data()

    def update_embed_data(self):
        self.multiplier = round(0.99 / self.probability, 2)
    
    def get_embed(self):
        embed = discord.Embed(title="🎰 도박 설정", color=discord.Color.blue())
        embed.add_field(name="배팅 금액", value=f"{self.amount:,}원", inline=True)
        embed.add_field(name="성공 확률", value=f"{int(self.probability*100)}%", inline=True)
        embed.add_field(name="예상 배당", value=f"{self.multiplier}배", inline=True)
        embed.set_footer(text="최대 확률: 50% | 최소 배팅: 1,000원")
        return embed

    @discord.ui.button(label="금액 변경 (x2)", style=discord.ButtonStyle.secondary, row=0)
    async def change_amount(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.amount * 2 > self.economy.get_balance(self.user_id):
            self.amount = 1000 
        else:
            self.amount *= 2
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="확률 변경 (-10%)", style=discord.ButtonStyle.secondary, row=0)
    async def change_prob(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.probability -= 0.1
        if self.probability <= 0.05:
            self.probability = 0.5
        self.update_embed_data()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="직접 입력", style=discord.ButtonStyle.primary, row=0)
    async def custom_input(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomInputModal(self))

    @discord.ui.button(label="게임 시작", style=discord.ButtonStyle.green, row=1)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verify balance again
        if self.economy.get_balance(self.user_id) < self.amount:
             await interaction.response.send_message("잔액이 부족합니다!", ephemeral=True)
             return
        
        # Switch to Game View
        game_view = GambleView(self.user_id, self.economy, self.amount, self.probability)
        await interaction.response.edit_message(embed=None, view=game_view, content="게임을 시작합니다...")
        
class Game(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.economy = EconomyService.get_instance()

    @discord.app_commands.command(name="잔액", description="자신의 현재 잔액을 확인합니다.")
    async def balance(self, interaction: discord.Interaction):
        bal = self.economy.get_balance(interaction.user.id)
        await interaction.response.send_message(f"💰 {interaction.user.mention}님의 잔액: **{bal:,}원**")

    @discord.app_commands.command(name="지원금", description="테스트용 지원금 5,000원을 받습니다.")
    async def give(self, interaction: discord.Interaction):
        self.economy.add_balance(interaction.user.id, 5000)
        await interaction.response.send_message("💵 지원금 **5,000원**이 지급되었습니다!")

    @discord.app_commands.command(name="랭킹", description="보유 금액 랭킹 TOP 10을 확인합니다.")
    async def leaderboard(self, interaction: discord.Interaction):
        rankings = self.economy.get_leaderboard()
        embed = discord.Embed(title="🏆 부자 랭킹 TOP 10", color=discord.Color.gold())
        for idx, (uid, bal) in enumerate(rankings, 1):
            user = await self.bot.fetch_user(int(uid))
            name = user.name if user else "Unknown"
            embed.add_field(name=f"{idx}위. {name}", value=f"{bal:,}원", inline=False)
        await interaction.response.send_message(embed=embed)

    @discord.app_commands.command(name="도박", description="돈을 걸고 도박을 합니다.")
    async def gamble(self, interaction: discord.Interaction):
        view = SettingsView(interaction.user.id, self.economy, None)
        await interaction.response.send_message(embed=view.get_embed(), view=view)

    @discord.app_commands.command(name="퀘스트", description="현재 진행 중인 퀘스트를 확인합니다.")
    async def quest(self, interaction: discord.Interaction):
        quest = self.economy.get_quest(interaction.user.id)
        if not quest:
            await interaction.response.send_message("현재 진행 중인 퀘스트가 없습니다.", ephemeral=True)
            return
        
        embed = discord.Embed(title="📜 현재 퀘스트", color=discord.Color.purple())
        if quest["type"] == "win_streak":
            embed.description = f"**{quest['target']}연승 도전**"
            embed.add_field(name="진행 상황", value=f"{quest['current']} / {quest['target']} 회", inline=True)
            embed.add_field(name="성공 보상", value=f"+{quest['reward']:,}원", inline=True)
            embed.add_field(name="실패 페널티", value=f"-{quest['penalty']:,}원", inline=True)
        
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Game(bot))