# cogs/persistent_panels.py
import discord
from discord.ext import commands, tasks
import asyncio

class PersistentPanels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.refresh_loop.start()

    def cog_unload(self):
        self.refresh_loop.cancel()

    @tasks.loop(minutes=15)
    async def refresh_loop(self):
        try:
            panels = await self.bot.db.get_persistent_panels()
            for p in panels:
                try:
                    ch = self.bot.get_channel(p["channel_id"])
                    if not ch: continue
                    msg = await ch.fetch_message(p["message_id"])
                    if not msg: continue
                    if p["panel_type"] == "leaderboard":
                        page = p["data"].get("page", 1)
                        per_page = p["data"].get("per_page", 10)
                        # reuse points.create_leaderboard_embed
                        from cogs.points import create_leaderboard_embed, LeaderboardView
                        embed = await create_leaderboard_embed(self.bot, page=page, per_page=per_page)
                        total_pages = max(1, (len(await self.bot.db.get_leaderboard())+per_page-1)//per_page)
                        view = LeaderboardView(self.bot, page, total_pages, per_page)
                        await msg.edit(embed=embed, view=view)
                    await asyncio.sleep(0.3)  # stagger edits
                except discord.NotFound:
                    await self.bot.db.delete_persistent_panel(p["message_id"])
                except Exception:
                    pass
        except Exception:
            pass

    @refresh_loop.before_loop
    async def before_refresh(self):
        await self.bot.wait_until_ready()

    @commands.slash_command(name="persistent_leaderboard")
    async def persistent_leaderboard(self, ctx: discord.ApplicationContext, page: discord.Option(int, default=1, required=False)):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("No permission.", ephemeral=True); return
        from cogs.points import create_leaderboard_embed, LeaderboardView
        per_page = 10
        rows = await self.bot.db.get_leaderboard()
        if not rows:
            await ctx.respond("Leaderboard empty.")
            return
        total_pages = max(1, (len(rows)+per_page-1)//per_page)
        embed = await create_leaderboard_embed(self.bot, page=page, per_page=per_page)
        view = LeaderboardView(self.bot, page, total_pages, per_page)
        resp = await ctx.respond(embed=embed, view=view)
        if hasattr(resp, "message"):
            msg = resp.message
        else:
            # py-cord returns the message in followup sometimes; attempt to fetch last message
            msg = (await ctx.original_response())
        await self.bot.db.save_persistent_panel(ctx.channel.id, msg.id, "leaderboard", {"page": page, "per_page": per_page, "total_pages": total_pages})
        await ctx.followup.send("Persistent leaderboard created (auto-refresh).", ephemeral=True)

    @commands.slash_command(name="list_panels")
    async def list_panels(self, ctx: discord.ApplicationContext):
        if not ctx.user.guild_permissions.administrator:
            await ctx.respond("No permission.", ephemeral=True); return
        panels = await self.bot.db.get_persistent_panels()
        if not panels:
            await ctx.respond("No panels saved.", ephemeral=True); return
        lines = []
        for p in panels:
            ch = self.bot.get_channel(p["channel_id"])
            lines.append(f"- {p['panel_type']} in {ch.mention if ch else p['channel_id']} msg {p['message_id']}")
        await ctx.respond("\n".join(lines), ephemeral=True)

def setup(bot):
    bot.add_cog(PersistentPanels(bot))
