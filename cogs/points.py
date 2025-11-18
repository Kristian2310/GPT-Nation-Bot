# cogs/points.py
import discord
from discord.ext import commands
from discord.ui import View, Button

ACCENT = 0x5865F2

async def create_leaderboard_embed(bot, page=1, per_page=10):
    rows = await bot.db.get_leaderboard()
    total_pages = max(1, (len(rows)+per_page-1)//per_page)
    page = max(1, min(page, total_pages))
    start = (page-1)*per_page
    slice_ = rows[start:start+per_page]
    lines = []
    guild = bot.guilds[0] if bot.guilds else None
    for idx,(uid,pts) in enumerate(slice_, start=start+1):
        member = guild.get_member(uid) if guild else None
        name = member.display_name if member else f"<@{uid}>"
        lines.append(f"#{idx} {name} — **{pts} pts**")
    embed = discord.Embed(title="🏆 Leaderboard", description="\n".join(lines) or "No entries", color=ACCENT)
    embed.set_footer(text=f"Page {page}/{total_pages}")
    return embed

class LeaderboardView(View):
    def __init__(self, bot, page, total_pages, per_page):
        super().__init__(timeout=120)
        self.bot = bot
        self.page = page
        self.total_pages = total_pages
        self.per_page = per_page

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="◀️")
    async def prev(self, b, inter):
        if self.page<=1:
            await inter.response.defer()
            return
        self.page -=1
        embed = await create_leaderboard_embed(self.bot, page=self.page, per_page=self.per_page)
        await inter.response.edit_message(embed=embed, view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, emoji="▶️")
    async def next(self, b, inter):
        if self.page>=self.total_pages:
            await inter.response.defer()
            return
        self.page +=1
        embed = await create_leaderboard_embed(self.bot, page=self.page, per_page=self.per_page)
        await inter.response.edit_message(embed=embed, view=self)

class PointsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="points")
    async def points(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User, required=False)):
        target = user or ctx.user
        pts = await self.bot.db.get_points(target.id)
        embed = discord.Embed(title=f"🏅 Points for {target.display_name}", description=f"**{pts} points**", color=ACCENT)
        if target.display_avatar:
            embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.respond(embed=embed)

    @commands.slash_command(name="leaderboard")
    async def leaderboard(self, ctx: discord.ApplicationContext, page: discord.Option(int, default=1, required=False)):
        rows = await self.bot.db.get_leaderboard()
        if not rows:
            await ctx.respond("Leaderboard is empty.")
            return
        per_page = 10
        total_pages = max(1, (len(rows)+per_page-1)//per_page)
        embed = await create_leaderboard_embed(self.bot, page=page, per_page=per_page)
        view = LeaderboardView(self.bot, page, total_pages, per_page)
        await ctx.respond(embed=embed, view=view)

    @commands.slash_command(name="points_add")
    async def points_add(self, ctx: discord.ApplicationContext, user: discord.Option(discord.User), amount: discord.Option(int)):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("No permission.", ephemeral=True); return
        cur = await self.bot.db.get_points(user.id)
        await self.bot.db.set_points(user.id, cur+amount)
        await ctx.respond(f"Added {amount} points to {user.mention}.")

    @commands.slash_command(name="points_reset")
    async def points_reset(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("No permission.", ephemeral=True); return
        await self.bot.db.reset_points()
        await ctx.respond("Leaderboard reset.")

def setup(bot):
    bot.add_cog(PointsCog(bot))
