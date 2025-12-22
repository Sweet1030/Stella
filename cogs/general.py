import discord
from discord import app_commands
from discord.ext import commands

class HelpSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot = bot
        options = []
        
        # 모든 코그의 커맨드를 수집
        self.all_commands = {}
        # 코그 이름으로 정렬
        sorted_cogs = sorted(bot.cogs.items(), key=lambda x: x[0])
        
        for cog_name, cog in sorted_cogs:
            # 커맨드 이름으로 정렬
            commands = sorted(cog.get_app_commands(), key=lambda c: c.name)
            for cmd in commands:
                # 그룹 커맨드(서브 커맨드가 있는 경우) 처리
                if isinstance(cmd, app_commands.Group):
                    sorted_subcommands = sorted(cmd.commands, key=lambda c: c.name)
                    for sub in sorted_subcommands:
                        full_name = f"{cmd.name} {sub.name}"
                        self.all_commands[full_name] = sub
                        
                        desc = sub.description[:90] + "..." if len(sub.description) > 90 else sub.description
                        options.append(discord.SelectOption(
                            label=f"/{full_name}",
                            description=desc,
                            value=full_name
                        ))
                else:
                    self.all_commands[cmd.name] = cmd
                    desc = cmd.description[:90] + "..." if len(cmd.description) > 90 else cmd.description
                    options.append(discord.SelectOption(
                        label=f"/{cmd.name}",
                        description=desc,
                        value=cmd.name
                    ))
        
        # 최대 25개 제한 (디스코드 UI 한계)
        # 25개가 넘어가면 페이지네이션이 필요하지만, 현재는 25개 미만이므로 슬라이싱만 처리
        options = options[:25]
        
        super().__init__(
            placeholder="명령어를 선택하여 상세 정보를 확인하세요.",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        cmd_key = self.values[0]
        cmd = self.all_commands.get(cmd_key)
        
        if not cmd:
            await interaction.response.send_message("❌ 명령어를 찾을 수 없습니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"/{cmd_key} 상세 정보",
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

        sorted_cogs = sorted(self.bot.cogs.items(), key=lambda x: x[0])
        for name, cog in sorted_cogs:
            commands_list = []
            sorted_commands = sorted(cog.get_app_commands(), key=lambda c: c.name)
            for cmd in sorted_commands:
                if isinstance(cmd, app_commands.Group):
                    sorted_subcommands = sorted(cmd.commands, key=lambda c: c.name)
                    for sub in sorted_subcommands:
                        commands_list.append(f"`/{cmd.name} {sub.name}`")
                else:
                    commands_list.append(f"`/{cmd.name}`")
            
            if commands_list:
                value_text = ", ".join(commands_list)
                embed.add_field(name=f"📂 {name}", value=value_text, inline=False)
        
        view = HelpView(self.bot)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(General(bot))
