import discord
from discord.ext import commands
import aiohttp
import asyncio
import time
import json
from config import computerurl, phoneurl, system_prompt
from anthropic import Anthropic


class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_history = {}
        self.last_activity = {}
        self.cooldowns = {}
        self.loading_icon = "<a:dopamineloading:1478835080725270641> "

        self.pc_lock = asyncio.Lock()
        self.phone_lock = asyncio.Lock()

    def _manage_history(self, guild_id):
        current_time = time.time()
        if guild_id in self.last_activity and (current_time - self.last_activity[guild_id] > 600):
            self.message_history[guild_id] = []

        self.last_activity[guild_id] = current_time
        if guild_id not in self.message_history:
            self.message_history[guild_id] = []

    def _count_tokens(self, history):
        response = self.client.beta.messages.count_tokens(
            model="claude-3-5-sonnet-20240620",
            messages=history
        )
        return response.input_tokens

    def _trim_to_tokens(self, guild_id, max_tokens=1750):
        if guild_id not in self.message_history:
            return

        while self._count_tokens(self.message_history[guild_id]) > max_tokens and len(
                self.message_history[guild_id]) > 1:
            self.message_history[guild_id].pop(0)
    async def _typing_indicator_task(self, channel, stop_event):
        try:
            while not stop_event.is_set():
                async with channel.typing():
                    try:
                        await asyncio.wait_for(stop_event.wait(), timeout=10.0)
                    except asyncio.TimeoutError:
                        continue
        except asyncio.CancelledError:
            pass

    def _format_response_payload(self, text, is_final=False):
        color = discord.Colour(0x944ae8)
        loading_prefix = self.loading_icon if not is_final else None

        if len(text) > 8000:
            text = text[:8000] + "\n\n*(Discord limits reached!)*"

        content = None
        embeds = []

        if len(text) <= 2000:
            content = f"### {loading_prefix} Dopamine is Thinking...\n{text}" if loading_prefix else text

        elif len(text) <= 4000:
            embed = discord.Embed(description= f"## {loading_prefix} Dopamine is Thinking...\n" + text if loading_prefix else text, colour=color)
            embeds.append(embed)

        elif len(text) <= 6000:
            e1 = discord.Embed(description=f"## {loading_prefix} Dopamine is Thinking...\n" + text[:4000] if loading_prefix else text[:4000], colour=color)
            e2 = discord.Embed(description=text[4000:], colour=color)
            embeds = [e1, e2]

        else:
            content = text[:2000]
            if loading_prefix: content = f"### {loading_prefix} Dopamine is Thinking...\n{content}"

            e1 = discord.Embed(description=text[2000:6000], colour=color)
            e2 = discord.Embed(description=text[6000:], colour=color)
            embeds = [e1, e2]

        return content, embeds

    async def _process_stream(self, response, message, stop_typing_event):
        full_content = ""
        msg_obj = None
        last_update = time.time()

        async for line in response.content:
            line = line.decode('utf-8').strip()
            if not line or line == "data: [DONE]":
                continue

            if line.startswith("data: "):
                if not stop_typing_event.is_set():
                    stop_typing_event.set()

                try:
                    data = json.loads(line[6:])
                    delta = data['choices'][0].get('delta', {}).get('content') or ""
                    full_content += delta
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

            current_time = time.time()
            if current_time - last_update >= 5.0 and full_content.strip():
                content, embeds = self._format_response_payload(full_content, is_final=False)
                try:
                    if msg_obj is None:
                        msg_obj = await message.reply(content=content, embeds=embeds)
                    else:
                        await msg_obj.edit(content=content, embeds=embeds)
                except discord.HTTPException:
                    pass
                last_update = current_time

        if full_content:
            content, embeds = self._format_response_payload(full_content, is_final=True)
            try:
                if msg_obj is None:
                    await message.reply(content=content, embeds=embeds)
                else:
                    await msg_obj.edit(content=content, embeds=embeds)
            except discord.HTTPException:
                await message.channel.send("Error: Response was too large to format properly.")

        return full_content

    async def _run_phone_request(self, session, guild_id, message, stop_typing_event, history_snapshot):
        history = history_snapshot.copy()
        if history:
            first_user_content = history[0]["content"]
            history[0]["content"] = f"INSTRUCTIONS: {system_prompt}\n\nUSER PROMPT: {first_user_content}"

        phone_payload = {
            "messages": history,
            "stream": True,
            "max_tokens": 4098,
            "temperature": 0.3
        }

        phone_timeout = aiohttp.ClientTimeout(sock_connect=5, sock_read=60)
        async with session.post(phoneurl, json=phone_payload, timeout=phone_timeout) as resp:
            if resp.status == 200:
                return await self._process_stream(resp, message, stop_typing_event)
            else:
                return None

    async def _is_server_online(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(total=1.0)
                async with session.get(url, timeout=timeout) as resp:
                    return True
        except:
            return False

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if self.bot.user in message.mentions:
            prompt = message.content
            for mention in message.mentions:
                prompt = prompt.replace(mention.mention, "")

            prompt = f"USER's PROMPT (User's name is {message.author.display_name}): " + prompt.replace(f"<@!{self.bot.user.id}>", "").strip()

            if not prompt:
                return

            if message.reference and message.reference.resolved:
                ref_msg = message.reference.resolved

                if ref_msg.author.id == self.bot.user.id:
                    quoted_content = ref_msg.content

                    prompt = (
                        f"CONTEXT: The user is quoting/replying to a previous message from YOU, Dopamine:\n"
                        f"--- QUOTED MESSAGE ---\n{quoted_content}\n--- END QUOTE ---\n\n"
                        f"USER'S PROMPT (User's name is {message.author.display_name}): {prompt}"
                    )
                else:
                    quoted_content = ref_msg.content
                    author_name = ref_msg.author.display_name


                    prompt = (
                        f"CONTEXT: The following is a message from {author_name} that the user is quoting/replying to:\n"
                        f"--- QUOTED MESSAGE ---\n{quoted_content}\n--- END QUOTE ---\n\n"
                        f"USER'S PROMPT (User's name is {message.author.display_name}): {prompt}"
                    )

            guild_id = message.guild.id
            current_time = time.time()

            if guild_id in self.cooldowns:
                last_time, duration = self.cooldowns[guild_id]
                if current_time < (last_time + duration):
                    remaining = int((last_time + duration) - current_time)
                    await message.reply(f"The server is on cooldown for {remaining} more seconds!", delete_after=5)
                    return

            self._manage_history(guild_id)

            new_user_message = {"role": "user", "content": prompt}

            current_context = self.message_history[guild_id].copy()
            current_context.append(new_user_message)

            self.message_history[guild_id].append(new_user_message)
            self._trim_to_tokens(guild_id, max_tokens=1750)

            stop_typing_event = asyncio.Event()
            typing_task = asyncio.create_task(self._typing_indicator_task(message.channel, stop_typing_event))
            start_time = time.time()
            final_response_text = None

            pc_online = await self._is_server_online(computerurl)
            phone_online = await self._is_server_online(phoneurl)

            target_lock = None
            use_phone = False

            if pc_online and not self.pc_lock.locked():
                target_lock = self.pc_lock

            elif pc_online and self.pc_lock.locked() and phone_online and not self.phone_lock.locked():
                target_lock = self.phone_lock
                use_phone = True

            elif not pc_online and phone_online:
                if not self.phone_lock.locked():
                    target_lock = self.phone_lock
                    use_phone = True
                else:
                    queue_msg = await message.reply(f"{self.loading_icon}Thinking...")
                    target_lock = self.phone_lock
                    use_phone = True
                    await target_lock.acquire()
                    try:
                        await queue_msg.delete()
                    except:
                        pass

            elif pc_online:
                queue_msg = await message.reply(f"{self.loading_icon}Thinking...")
                target_lock = self.pc_lock
                await target_lock.acquire()
                try:
                    await queue_msg.delete()
                except:
                    pass

            else:
                await message.reply(
                    "Error: Local servers seem to be unavailable! Please try again later.")
                return

            if not target_lock.locked():
                await target_lock.acquire()

            try:
                async with aiohttp.ClientSession() as session:
                    if not use_phone:
                        pc_payload = {
                            "model": "google-gemma-3-4b-it-qat-small-fix",
                            "messages": current_context,
                            "stream": True,
                            "max_tokens": 4096
                        }
                        try:
                            pc_timeout = aiohttp.ClientTimeout(sock_connect=2, sock_read=60)
                            async with session.post(computerurl, json=pc_payload, timeout=pc_timeout) as resp:
                                if resp.status == 200:
                                    final_response_text = await self._process_stream(resp, message, stop_typing_event)
                                else:
                                    use_phone = True
                        except Exception:
                            use_phone = True

                    if use_phone:
                        if target_lock == self.pc_lock:
                            target_lock.release()
                            async with self.phone_lock:
                                try:
                                    final_response_text = await self._run_phone_request(session, guild_id, message, stop_typing_event, current_context)
                                except Exception:
                                    await message.reply("Error: Local servers seem to be unavailable! Please try again later.")
                        else:
                            try:
                                final_response_text = await self._run_phone_request(session, guild_id, message,
                                                                                    stop_typing_event)
                            except Exception:
                                await message.reply("Error: Local servers seem to be unavailable! Please try again later.")

            finally:
                if target_lock.locked():
                    target_lock.release()
                stop_typing_event.set()
                typing_task.cancel()

            if final_response_text:
                self.message_history[guild_id].append({"role": "assistant", "content": final_response_text})
                self._trim_to_tokens(guild_id, max_tokens=1750)

                generation_time = time.time() - start_time
                self.cooldowns[guild_id] = (time.time(), generation_time)


async def setup(bot):
    await bot.add_cog(AICog(bot))