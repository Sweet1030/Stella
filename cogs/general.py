import discord
from discord import app_commands
from discord.ext import commands

class HelpSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = []
        
        # 모든 코그의 커맨드를 수집
        self.all_commands = {}
        for cog_name, cog in bot.cogs.items():
            for cmd in cog.get_app_commands():
                self.all_commands[cmd.name] = cmd
                # description이 너무 길면 자름
                desc = cmd.description[:90] + "..." if len(cmd.description) > 90 else cmd.description
                options.append(discord.SelectOption(
                    label=f"/{cmd.name}",
                    description=desc,
                    value=cmd.name
                ))
        
        # 최대 25개 제한 (디스코드 UI 한계)
        options = options[:25]
        
        super().__init__(
            placeholder="명령어를 선택하여 상세 정보를 확인하세요.",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        cmd_name = self.values[0]
        cmd = self.all_commands.get(cmd_name)
        
        if not cmd:
            await interaction.response.send_message("❌ 명령어를 찾을 수 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"/{cmd.name} 상세 정보",
            description=cmd.description,
            color=discord.Color.blue()
        )
        
        # 매개변수 정보 추가
        if cmd.parameters:
            params_text = ""
            for param in cmd.parameters:
                required = "필수" if param.required else "선택"
                params_text += f"• **{param.name}** ({required}): {param.description}\n"
            embed.add_field(name="매개변수", value=params_text, inline=False)
        else:
            embed.add_field(name="매개변수", value="없음", inline=False)
            
        # 팁 추가
        embed.set_footer(text="메뉴에서 다른 명령어를 선택하여 정보를 확인할 수 있습니다.")
        
        await interaction.response.edit_message(embed=embed)

class HelpView(discord.ui.View):
    def __init__(self, bot, timeout=180):
        super().__init__(timeout=timeout)
        self.add_item(HelpSelect(bot))

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="핑", description="봇의 응답 속도를 확인합니다.")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="🏓 퐁!",
            description=f"현재 핑: **{latency}ms**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="도움말", description="사용 가능한 모든 명령어를 확인합니다.")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📘 도움말",
            description="아래 메뉴에서 명령어를 선택하여 상세 정보를 확인하세요.",
            color=discord.Color.blue()
        )

        # 기본 목록 표시 (카테고리별)
        for name, cog in self.bot.cogs.items():
            commands = cog.get_app_commands()
            if commands:
                command_list = [f"`/{cmd.name}`" for cmd in commands]
                value_text = ", ".join(command_list)
                if value_text:
                    embed.add_field(name=f"📂 {name}", value=value_text, inline=False)
        
        view = HelpView(self.bot)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(General(bot))
