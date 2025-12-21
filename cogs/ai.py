import discord
from discord import app_commands
from discord.ext import commands
from openai import OpenAI
import config

class AI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)

    @app_commands.command(name="chat", description="AI와 대화합니다.")
    async def chat(self, interaction: discord.Interaction, message: str):
        await interaction.response.defer()
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant named Stella."},
                    {"role": "user", "content": message}
                ],
                max_tokens=300
            )
            
            ai_message = response.choices[0].message.content
            
            # Discord 메시지 길이 제한(2000자) 처리 필요시 추가 로직 구현
            if len(ai_message) > 2000:
                ai_message = ai_message[:1997] + "..."
                
            await interaction.followup.send(ai_message)
            
        except Exception as e:
            await interaction.followup.send(f"오류가 발생했습니다: {str(e)}")

async def setup(bot):
    await bot.add_cog(AI(bot))
