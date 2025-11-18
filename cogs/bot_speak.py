# cogs/bot_speak.py
import discord
from discord.ext import commands

def parse_color(s, default=0x5865F2):
    if not s: return default
    try:
        s = s.strip()
        return int(s.lstrip("#"), 16)
    except Exception:
        return default

class BotSpeak(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="talk")
    async def talk(self, ctx: discord.ApplicationContext, channel: discord.Option(str, "channel id or name"), content: discord.Option(str, "text"), as_embed: discord.Option(bool, default=True, required=False)):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("No permission.", ephemeral=True); return
        target = None
        if channel.isdigit():
            cid = int(channel)
            target = ctx.guild.get_channel(cid)
        if not target:
            for ch in ctx.guild.channels:
                if getattr(ch, "name", "") == channel:
                    target = ch; break
        if not target:
            await ctx.respond("Channel not found.", ephemeral=True); return
        if as_embed:
            embed = discord.Embed(description=content, color=parse_color(None))
            await target.send(embed=embed)
        else:
            await target.send(content)
        await ctx.respond("Sent.", ephemeral=True)

def setup(bot):
    bot.add_cog(BotSpeak(bot))
