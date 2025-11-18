# cogs/audit_log.py
import discord
from discord.ext import commands
from collections import deque
from datetime import datetime

class AuditLog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._recent = deque(maxlen=1024)

    async def _get_audit_channel(self, guild):
        cfg = await self.bot.db.load_config("audit_channel")
        ch_id = (cfg or {}).get("id")
        if not ch_id:
            return None
        return guild.get_channel(int(ch_id))

    def _flatten_options(self, options):
        if not options:
            return []
        tokens = []
        for opt in options:
            t = opt.get("type")
            n = opt.get("name")
            if t in (1,2):
                if n: tokens.append(str(n))
                tokens.extend(self._flatten_options(opt.get("options")))
            else:
                if n is not None:
                    v = opt.get("value")
                    tokens.append(f"{n}={v}")
        return tokens

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        try:
            if interaction.type != discord.InteractionType.application_command or not interaction.guild:
                return
            if interaction.id in self._recent:
                return
            self._recent.append(interaction.id)
            data = interaction.data or {}
            name = data.get("name", "unknown")
            tokens = self._flatten_options(data.get("options") or [])
            path = " ".join([name] + [t for t in tokens if "=" not in t])
            args = " ".join([t for t in tokens if "=" in t]) or "no-args"
            target = await self._get_audit_channel(interaction.guild) or interaction.channel
            if not target: return
            utc_now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            msg = f"🛡️ [{utc_now}] /{path} by {interaction.user.mention} args: {args}"
            try:
                await target.send(msg)
            except discord.Forbidden:
                pass
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            if message.author.bot or not message.guild:
                return
            prefix = (await self.bot.db.load_config("prefix") or {}).get("value", "!")
            content = (message.content or "").strip()
            if not content.startswith(prefix): return
            trigger = content.split()[0][len(prefix):] or ""
            target = await self._get_audit_channel(message.guild) or message.channel
            if not target: return
            utc_now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            await target.send(f"🛡️ [{utc_now}] {prefix}{trigger} by {message.author.mention} in {message.channel.mention}")
        except Exception:
            pass

def setup(bot):
    bot.add_cog(AuditLog(bot))
