# cogs/verification.py
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, InputText
from datetime import datetime

class VerificationModal(Modal):
    def __init__(self, category_id=None):
        super().__init__(title="Verification")
        self.add_item(InputText(label="In-game name", required=True))
        self.add_item(InputText(label="Invited by", required=False))
        self.category_id = category_id

    async def on_submit(self, inter):
        await inter.response.defer(ephemeral=True)
        guild = inter.guild
        parent = None
        cfg = await inter.client.db.load_config("verification_category")
        cid = (cfg or {}).get("id")
        if cid:
            cand = guild.get_channel(int(cid))
            parent = cand if isinstance(cand, discord.CategoryChannel) else None
        overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False),
                      inter.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)}
        ch = await guild.create_text_channel(f"verify-{inter.user.name}".lower()[:90], overwrites=overwrites, category=parent, reason="Verification")
        embed = discord.Embed(title="Verification Request", description=f"Requester: {inter.user.mention}", timestamp=datetime.utcnow())
        embed.add_field("In-game name", self.children[0].value)
        embed.add_field("Invited by", self.children[1].value or "—")
        await ch.send(content=f"{inter.user.mention}", embed=embed)
        await inter.followup.send(f"Verification channel created: {ch.mention}", ephemeral=True)

class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="verification_panel")
    async def verification_panel(self, ctx: discord.ApplicationContext):
        view = View(timeout=None)
        class VButton(Button):
            def __init__(self):
                super().__init__(label="Verify", style=discord.ButtonStyle.green, custom_id="verify_open")
            async def callback(self, inter):
                await inter.response.send_modal(VerificationModal())
        view.add_item(VButton())
        embed = discord.Embed(title="Verification Panel", description="Click Verify and follow instructions.", color=discord.Color.green())
        await ctx.respond(embed=embed, view=view)

def setup(bot):
    bot.add_cog(VerificationCog(bot))
