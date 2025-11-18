# cogs/tickets.py
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, InputText
from datetime import datetime
import asyncio

DEFAULT_QUESTIONS = ["In-game name?*", "Server name?*", "Room?*", "Anything else?"]
DEFAULT_POINTS = 5
active_tickets = {}

def parse_required(label):
    raw = label.strip()
    req = raw.endswith("*") or raw.startswith("*")
    cleaned = raw.strip("* ").strip()
    return cleaned, req

class TicketModal(Modal):
    def __init__(self, category, questions, requestor_id, slots):
        super().__init__(title=f"{category} Ticket")
        self.category = category
        self.requestor_id = requestor_id
        self.slots = slots
        for q in (questions or [])[:5]:
            lbl, req = parse_required(q)
            self.add_item(InputText(label=lbl, style=discord.InputTextStyle.short, required=req))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            # ticket number
            num = await self.view.bot.db.increment_ticket_number(self.category)
            name = f"{self.category.lower().replace(' ','-')}-{num}"
            guild = interaction.guild
            overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False),
                          interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)}
            ch = await guild.create_text_channel(name, overwrites=overwrites, reason=f"Ticket created by {interaction.user}")
            embed = discord.Embed(title=f"🎫 {self.category} #{num}", description=f"Requester: {interaction.user.mention}", color=0x00FF00, timestamp=datetime.utcnow())
            answers = {}
            for child in self.children:
                label = child.label
                val = child.value or "—"
                answers[label] = val
                embed.add_field(name=label, value=(val if not label.lower().startswith("room") else "Revealed after joining"), inline=False)
            for i in range(self.slots):
                embed.add_field(name=f"👤 Helper Slot {i+1}", value="Empty", inline=True)
            view = TicketView(self.category, interaction.user.id)
            msg = await ch.send(content="", embed=embed, view=view)
            active_tickets[ch.id] = {"category": self.category, "requestor": interaction.user.id, "helpers":[None]*self.slots, "embed_msg": msg, "answers": answers, "closed_stage":0}
            await interaction.followup.send(f"Ticket created: {ch.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Ticket creation failed: {e}", ephemeral=True)

class TicketView(View):
    def __init__(self, category, requestor_id):
        super().__init__(timeout=None)
        self.category = category
        self.requestor_id = requestor_id
        self.add_item(Button(label="Join", style=discord.ButtonStyle.green, custom_id="join_ticket", emoji="➕"))
        self.add_item(Button(label="Close", style=discord.ButtonStyle.gray, custom_id="close_ticket", emoji="🧹"))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="panel")
    async def panel(self, ctx: discord.ApplicationContext):
        # show ticket panel with default categories
        categories = [{"name": "Default", "questions": DEFAULT_QUESTIONS, "slots": 3}]
        view = View(timeout=None)
        class Select(discord.ui.Select):
            def __init__(self, categories):
                options = [discord.SelectOption(label=c["name"]) for c in categories]
                super().__init__(placeholder="Choose a ticket type...", min_values=1, max_values=1, options=options)
            async def callback(self, inter):
                chosen = self.values[0]
                cat = next((c for c in categories if c["name"]==chosen), categories[0])
                await inter.response.send_modal(TicketModal(cat["name"], cat["questions"], inter.user.id, cat.get("slots",3)))
        view.add_item(Select(categories))
        embed = discord.Embed(title="🎮 In-game Assistance", description="Select a service to create a ticket.", color=0x5865F2)
        await ctx.respond(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component: return
        if not interaction.channel: return
        ticket = active_tickets.get(interaction.channel.id)
        if not ticket: return
        cid = interaction.data.get("custom_id")
        if cid == "join_ticket":
            if interaction.user.id == ticket["requestor"]:
                await interaction.response.send_message("You cannot join your own ticket.", ephemeral=True); return
            if interaction.user.id in [h for h in ticket["helpers"] if h]:
                await interaction.response.send_message("You're already a helper.", ephemeral=True); return
            for i in range(len(ticket["helpers"])):
                if ticket["helpers"][i] is None:
                    ticket["helpers"][i] = interaction.user.id
                    break
            # grant channel permission
            try:
                await interaction.channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
            except Exception:
                pass
            # edit embed
            try:
                embed = ticket["embed_msg"].embeds[0]
                base = len(embed.fields) - len(ticket["helpers"])
                for i, h in enumerate(ticket["helpers"]):
                    embed.set_field_at(base+i, name=f"Helper Slot {i+1}", value=(f"<@{h}>" if h else "Empty"), inline=True)
                await ticket["embed_msg"].edit(embed=embed)
            except Exception:
                pass
            await interaction.response.send_message("You joined the ticket (ephemeral).", ephemeral=True)
        elif cid == "close_ticket":
            # simple two-click close flow
            is_requestor = interaction.user.id == ticket["requestor"]
            is_staff = interaction.user.guild_permissions.administrator
            if not (is_requestor or is_staff):
                await interaction.response.send_message("Only staff or requestor can close.", ephemeral=True); return
            stage = ticket.get("closed_stage",0)
            if stage == 0:
                # remove helpers access
                helpers = [h for h in ticket["helpers"] if h]
                for uid in helpers:
                    try:
                        member = interaction.guild.get_member(uid)
                        if member:
                            await interaction.channel.set_permissions(member, view_channel=False)
                    except Exception:
                        pass
                ticket["closed_stage"] = 1
                await interaction.response.send_message("Helpers removed. Click close again to finalize.", ephemeral=True)
            else:
                # finalize: transcript and delete
                try:
                    await generate_transcript_and_send(ticket, interaction.channel, rewarded=False, bot=self.bot)
                except Exception:
                    pass
                active_tickets.pop(interaction.channel.id, None)
                try:
                    await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
                except Exception:
                    pass

async def generate_transcript_and_send(ticket, channel, rewarded=False, bot=None):
    # gather last 100 messages
    lines = []
    async for m in channel.history(limit=100, oldest_first=True):
        lines.append(f"[{m.created_at}] {m.author}: {m.content}")
    txt = f"Transcript for {ticket['category']}\n" + "\n".join(lines)
    # send to DB-configured transcript channel if set
    cfg = await bot.db.load_config("transcript_channel")
    ch_id = (cfg or {}).get("id")
    if ch_id:
        guild = channel.guild
        tch = guild.get_channel(int(ch_id))
        if tch:
            from io import StringIO
            f = discord.File(StringIO(txt), filename=f"transcript-{channel.name}.txt")
            await tch.send(embed=discord.Embed(title="Ticket transcript", description=f"Ticket: {ticket['category']}"), file=f)

def setup(bot):
    bot.add_cog(TicketCog(bot))
