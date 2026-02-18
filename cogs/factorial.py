import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import asyncio
import math
import re
import ast

from dopamineframework import mod_check

from config import FDB_PATH


class ConnectionPool:

    def __init__(self, db_path, max_connections=5):
        self.db_path = db_path
        self.max_connections = max_connections
        self.queue = asyncio.Queue(maxsize=max_connections)
        self.connections = []

    async def initialize(self):
        for _ in range(self.max_connections):
            conn = await aiosqlite.connect(self.db_path)
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            await conn.commit()
            self.connections.append(conn)
            await self.queue.put(conn)

    async def acquire(self):
        return await self.queue.get()

    async def release(self, conn):
        await self.queue.put(conn)

    async def close(self):
        for conn in self.connections:
            await conn.close()


class FactorialCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_pool = ConnectionPool(FDB_PATH, max_connections=5)
        self.disabled_cache = set()
        self.regex = re.compile(r'([0-9\.\+\-\*\/\(\)\^\s]+)!')

    async def cog_load(self):
        await self.db_pool.initialize()

        conn = await self.db_pool.acquire()
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS disabled_guilds (
                    guild_id INTEGER PRIMARY KEY
                )
            """)
            await conn.commit()

            async with conn.execute("SELECT guild_id FROM disabled_guilds") as cursor:
                rows = await cursor.fetchall()
                self.disabled_cache = {row[0] for row in rows}


        finally:
            await self.db_pool.release(conn)

    async def cog_unload(self):
        await self.db_pool.close()

    def safe_eval_math(self, expr_str):
        operators = {
            ast.Add: float.__add__,
            ast.Sub: float.__sub__,
            ast.Mult: float.__mul__,
            ast.Div: float.__truediv__,
            ast.Pow: float.__pow__,
            ast.USub: float.__neg__,
            ast.UAdd: float.__pos__
        }

        def eval_node(node):
            if isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.BinOp):
                left = eval_node(node.left)
                right = eval_node(node.right)
                return operators[type(node.op)](left, right)
            elif isinstance(node, ast.UnaryOp):
                operand = eval_node(node.operand)
                return operators[type(node.op)](operand)
            else:
                raise TypeError("Unsupported operation")

        try:
            cleaned_expr = expr_str.replace("^", "**").strip()
            return eval_node(ast.parse(cleaned_expr, mode='eval').body)
        except Exception:
            return None

    def calculate_factorial(self, n):
        try:
            if n < 0:
                return None, False

            if n > 3000:
                return None, False

            if n <= 40:
                if abs(n - round(n)) < 1e-9:
                    return str(math.factorial(int(round(n)))), False
                else:
                    res = math.gamma(n + 1)
                    return f"{res:.4f}", False

            log_factorial = math.lgamma(n + 1) / math.log(10)
            exponent = int(math.floor(log_factorial))
            mantissa_log = log_factorial - exponent
            mantissa = 10 ** mantissa_log

            return f"{mantissa:.4f} × 10^{exponent}", True

        except Exception as e:
            return None, False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if message.guild.id in self.disabled_cache:
            return

        match = self.regex.search(message.content)
        if not match:
            return

        math_string = match.group(1)

        number = self.safe_eval_math(math_string)

        if number is None or not isinstance(number, (int, float)):
            return

        result_str, is_sci = self.calculate_factorial(number)

        if result_str:
            clean_num = int(number) if number == int(number) else number
            await message.reply(f"{clean_num}! = {result_str}\n\nAccidentally Factorial! 🤓\n\n-# [What is a factorial?](<https://en.wikipedia.org/wiki/Factorial>)")

    @app_commands.command(name="factorial", description="Toggle accidental factorial detection for this server.")
    @app_commands.checks(mod_check)
    async def factorial_toggle(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        conn = await self.db_pool.acquire()

        try:
            async with conn.execute("SELECT 1 FROM disabled_guilds WHERE guild_id = ?", (guild_id,)) as cursor:
                exists = await cursor.fetchone()

            if exists:
                await conn.execute("DELETE FROM disabled_guilds WHERE guild_id = ?", (guild_id,))
                await conn.commit()

                if guild_id in self.disabled_cache:
                    self.disabled_cache.remove(guild_id)

                await interaction.response.send_message("Factorial detection has been **ENABLED** for this server.",
                                                        ephemeral=False)
            else:
                await conn.execute("INSERT OR IGNORE INTO disabled_guilds (guild_id) VALUES (?)", (guild_id,))
                await conn.commit()

                self.disabled_cache.add(guild_id)

                await interaction.response.send_message("Factorial detection has been **DISABLED** for this server.",
                                                        ephemeral=False)

        finally:
            await self.db_pool.release(conn)


async def setup(bot):
    await bot.add_cog(FactorialCog(bot))