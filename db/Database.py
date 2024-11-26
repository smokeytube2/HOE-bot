import aiosqlite
from datetime import datetime
import random

class Database:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_name="economy.db"):
        self.db_name = db_name

    async def initialize(self):
        """Initialize the database by creating the necessary table."""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
            CREATE TABLE IF NOT EXISTS user_data (
                member_id INTEGER PRIMARY KEY,
                candy INTEGER DEFAULT 0,
                last_work_time TEXT DEFAULT NULL,
                stealing_attempts INTEGER DEFAULT 0,
                last_shield_time TEXT DEFAULT NULL,
                work_multiplier REAL DEFAULT 1.0
            )
            ''')

            await db.execute('''
            CREATE TABLE IF NOT EXISTS lottery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candy_pot INTEGER DEFAULT 0
            )
            ''')

            await db.execute('''
            CREATE TABLE IF NOT EXISTS lottery_contributors (
                member_id INTEGER PRIMARY KEY,
                tickets INTEGER DEFAULT 0
            )
            ''')

            # Initialize the lottery pot if it is empty.
            cursor = await db.execute('SELECT COUNT(*) FROM lottery')
            row = await cursor.fetchone()
            if row[0] == 0:
                await db.execute("INSERT INTO lottery (candy_pot) VALUES (0)")

            await db.commit()

    async def add_or_update_user(self, member_id, candy=0, multiplier=1.0):
        """Add a new user or update an existing user's candy and multiplier."""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
            INSERT INTO user_data (member_id, candy, work_multiplier)
            VALUES (?, ?, ?)
            ON CONFLICT(member_id) DO UPDATE SET
                candy = candy + excluded.candy,
                work_multiplier = excluded.work_multiplier
            ''', (member_id, candy, multiplier))
            await db.commit()

    async def add_candy(self, member_id, amount):
        """Add or remove candy from a user."""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
            INSERT INTO user_data (member_id, candy)
            VALUES (?, ?)
            ON CONFLICT(member_id) DO UPDATE SET
                candy = candy + excluded.candy
            ''', (member_id, amount))
            await db.commit()

    async def update_last_work_time(self, member_id):
        """Update the last work time for a user."""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
            UPDATE user_data
            SET last_work_time = ?
            WHERE member_id = ?
            ''', (datetime.now().isoformat(), member_id))
            await db.commit()

    async def get_user_data(self, member_id):
        """Retrieve data for a specific user."""
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute('SELECT * FROM user_data WHERE member_id = ?', (member_id,))
            row = await cursor.fetchone()
            return row

    async def increment_stealing_attempts(self, member_id):
        """Increment the stealing attempts for a user."""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
            UPDATE user_data
            SET stealing_attempts = stealing_attempts + 1
            WHERE member_id = ?
            ''', (member_id,))
            await db.commit()

    async def update_last_shield_time(self, member_id):
        """Update the last shield time for a user."""
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute('''
            UPDATE user_data
            SET last_shield_time = ?
            WHERE member_id = ?
            ''', (datetime.now().isoformat(), member_id))
            await db.commit()

    # -------------- Lottery -------------- #

    async def add_to_lottery(self, member_id, tickets):
        """Add user's contribution to the lottery."""
        candy = tickets * 25
        async with aiosqlite.connect(self.db_name) as db:
            # Update lottery pot
            await db.execute('''
            UPDATE lottery SET candy_pot = candy_pot + ?
            ''', (candy,))

            await db.execute('''
            INSERT INTO lottery_contributors (member_id, tickets)
            VALUES (?, ?)
            ON CONFLICT(member_id) DO UPDATE SET
                tickets = tickets + excluded.tickets
            ''', (member_id, tickets))

            # Deduct candy from user
            await db.execute('''
            UPDATE user_data SET candy = candy - ? WHERE member_id = ?
            ''', (candy, member_id))

            await db.commit()

    async def get_lottery_pot(self):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute('SELECT candy_pot FROM lottery')
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_lottery_contributors(self):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute('SELECT * FROM lottery_contributors')
            return await cursor.fetchall()

    async def draw_lottery(self):
        async with aiosqlite.connect(self.db_name) as db:
            cursor = await db.execute('SELECT member_id, tickets FROM lottery_contributors')
            contributions = await cursor.fetchall()

            if not contributions:
                return None, 0

            tickets_pool = []
            for member_id, tickets in contributions:
                tickets_pool.extend([member_id] * tickets)

            winner_id = random.choice(tickets_pool)

            cursor = await db.execute('SELECT candy_pot FROM lottery')
            pot = (await cursor.fetchone())[0]

            await db.execute('''
            UPDATE user_data SET candy = candy + ? WHERE member_id = ?
            ''', (pot, winner_id))
            await db.execute('DELETE FROM lottery_contributors')
            await db.execute('UPDATE lottery SET candy_pot = 0')

            await db.commit()

            return winner_id, pot