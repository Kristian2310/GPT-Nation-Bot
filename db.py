# db.py
import os, json, asyncio
from pathlib import Path
import aiosqlite

DEFAULT_DB = "bot_data.db"
DB_FILE = os.getenv("DB_FILE", DEFAULT_DB)

class Database:
    def __init__(self):
        self.db = None
        self._lock = asyncio.Lock()
        self.backend = "sqlite"

    async def init(self):
        Path(DB_FILE).parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(DB_FILE)
        await self.db.execute("""CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)""")
        await self.db.execute("""CREATE TABLE IF NOT EXISTS user_points (user_id INTEGER PRIMARY KEY, points INTEGER)""")
        await self.db.execute("""CREATE TABLE IF NOT EXISTS persistent_panels (message_id INTEGER PRIMARY KEY, channel_id INTEGER, panel_type TEXT, data TEXT)""")
        await self.db.execute("""CREATE TABLE IF NOT EXISTS tickets_counter (category TEXT PRIMARY KEY, last_number INTEGER)""")
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()

    # Config helpers
    async def save_config(self, key, value):
        v = json.dumps(value)
        await self.db.execute("INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, v))
        await self.db.commit()

    async def load_config(self, key):
        async with self.db.execute("SELECT value FROM config WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return json.loads(row[0]) if row else None

    # Points
    async def set_points(self, user_id, points):
        await self.db.execute("INSERT INTO user_points(user_id, points) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET points=excluded.points", (int(user_id), int(points)))
        await self.db.commit()

    async def get_points(self, user_id):
        async with self.db.execute("SELECT points FROM user_points WHERE user_id = ?", (int(user_id),)) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def reset_points(self):
        await self.db.execute("DELETE FROM user_points")
        await self.db.commit()

    async def get_leaderboard(self, limit=None):
        q = "SELECT user_id, points FROM user_points ORDER BY points DESC"
        if limit:
            q += f" LIMIT {int(limit)}"
        async with self.db.execute(q) as cur:
            rows = await cur.fetchall()
            return [(int(r[0]), int(r[1])) for r in rows]

    async def delete_user_points(self, user_id):
        await self.db.execute("DELETE FROM user_points WHERE user_id = ?", (int(user_id),))
        await self.db.commit()

    # persistent panels
    async def save_persistent_panel(self, channel_id, message_id, panel_type, data):
        data_json = json.dumps(data)
        await self.db.execute("INSERT INTO persistent_panels(message_id, channel_id, panel_type, data) VALUES(?,?,?,?) ON CONFLICT(message_id) DO UPDATE SET data=excluded.data", (int(message_id), int(channel_id), panel_type, data_json))
        await self.db.commit()

    async def get_persistent_panels(self, panel_type=None):
        if panel_type:
            async with self.db.execute("SELECT message_id, channel_id, panel_type, data FROM persistent_panels WHERE panel_type = ?", (panel_type,)) as cur:
                rows = await cur.fetchall()
        else:
            async with self.db.execute("SELECT message_id, channel_id, panel_type, data FROM persistent_panels") as cur:
                rows = await cur.fetchall()
        return [{"message_id": r[0], "channel_id": r[1], "panel_type": r[2], "data": json.loads(r[3])} for r in rows]

    async def delete_persistent_panel(self, message_id):
        await self.db.execute("DELETE FROM persistent_panels WHERE message_id = ?", (int(message_id),))
        await self.db.commit()

    # ticket counter
    async def get_ticket_number(self, category):
        async with self.db.execute("SELECT last_number FROM tickets_counter WHERE category = ?", (category,)) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row else 0

    async def increment_ticket_number(self, category):
        last = await self.get_ticket_number(category) + 1
        await self.db.execute("INSERT INTO tickets_counter(category, last_number) VALUES(?,?) ON CONFLICT(category) DO UPDATE SET last_number=excluded.last_number", (category, last))
        await self.db.commit()
        return last
