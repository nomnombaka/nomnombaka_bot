from dotenv import load_dotenv
import discord
from discord.ext import commands
import os
import feedparser
import asyncio
from gtts import gTTS
import io
from google import genai
from google.genai import types
import yt_dlp
from typing import Any
from discord.ui import View, button
import functools
import base64

# LOAD ENV VARIABLES
load_dotenv()

# CONSTANTS
TWITTER_POSTS_CHANNEL_ID = 1495834413442011318
TWITTER_RSS = "https://nitter.net/r1ktx/rss"

YOUTUBE_VIDEOS_CHANNEL_ID = 1496108672768540734
YOUTUBE_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id=UCQJLTQrzErVvASGrVInfTAA"

YDL_OPTIONS: dict[str, Any] = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
}

FFMPEG_OPTIONS = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

last_twitter = None
last_youtube = None

# BOT SETUP
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
ai_client = genai.Client()

DEFAULT_AI_PERSONALITY = "You are the funny bro in everyone's friend circle. you use too much genz internet slangs."

class HelpView(View):
    def __init__(self):
        super().__init__(timeout=60)

    def get_embed(self, category):
        if category == "main":
            embed = discord.Embed(
                title="🛠️ Help Menu",
                description="Select a category below 👇",
                color=discord.Color.blue()
            )
            embed.add_field(name="🤖 AI", value="AI commands", inline=True)
            embed.add_field(name="🎵 Music", value="Music commands", inline=True)
            embed.add_field(name="🛡️ Moderation", value="Mod commands", inline=True)
            embed.set_footer(text="nomnombaka bot")
            return embed

        elif category == "ai":
            return discord.Embed(
                title="🤖 AI Commands",
                description="`!ai_chat <text> | <personality>`\nChat with AI",
                color=discord.Color.purple()
            )

        elif category == "music":
            return discord.Embed(
                title="🎵 Music Commands",
                description=(
                    "`!play_music <url/search>`\nPlay music\n"
                    "`!stop_music`\nStop music"
                ),
                color=discord.Color.green()
            )

        elif category == "mod":
            return discord.Embed(
                title="🛡️ Moderation Commands",
                description=(           	
                    "`!purge <user>`\n"
                    "`!change_nickname <user>`\n"
                    "`!reset_nickname <user>`\n"
                    "`!kick <user> <reason>`\n"
                    "`!ban <user> <reason>`\n"
                    "`!unban <user>`"
                ),
                color=discord.Color.red()
            )

    @button(label="Main", style=discord.ButtonStyle.gray)
    async def main_btn(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(embed=self.get_embed("main"), view=self)

    @button(label="AI", style=discord.ButtonStyle.blurple)
    async def ai_btn(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(embed=self.get_embed("ai"), view=self)

    @button(label="Music", style=discord.ButtonStyle.green)
    async def music_btn(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(embed=self.get_embed("music"), view=self)

    @button(label="Moderation", style=discord.ButtonStyle.red)
    async def mod_btn(self, interaction: discord.Interaction, button):
        await interaction.response.edit_message(embed=self.get_embed("mod"), view=self)



async def get_audio_url(query):
    loop = asyncio.get_event_loop()

    # 1. Handle Cookies from Environment Variable
    cookie_content = os.getenv("YOUTUBE_COOKIES")
    cookie_path = None

    if cookie_content:
        try:
            # Decode the base64 string
            decoded_cookies = base64.b64decode(cookie_content).decode('utf-8')
            # Write to a temporary file for yt-dlp to read
            cookie_path = 'cookies.txt'
            with open(cookie_path, 'w', encoding='utf-8') as f:
                f.write(decoded_cookies)
        except Exception as e:
            print(f"Cookie decoding failed: {e}")

    def extract():
        # Create a local copy of options to add the cookie file path
        opts = YDL_OPTIONS.copy()
        if cookie_path:
            opts['cookiefile'] = cookie_path

        with yt_dlp.YoutubeDL(opts) as ydl:
            if not query.startswith("http"):
                info = ydl.extract_info(f"ytsearch:{query}", download=False)
                return info['entries']
            else:
                return ydl.extract_info(query, download=False)

    data = await loop.run_in_executor(None, extract)
    return data['url'], data.get('title', 'Unknown Title')

# ---------------- AI ----------------

async def ai_text_response(prompt, personality):
    try:
        loop = asyncio.get_event_loop()
        final_personality = personality if personality else DEFAULT_AI_PERSONALITY
        response = await loop.run_in_executor(
            None,
            lambda: ai_client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[f"[RESPONSE MUST BE UNDER 2000 WORDS.] {prompt}"],
                config=types.GenerateContentConfig(
                    system_instruction=f"{final_personality}"
                    )
                ),
        )

        return response.text

    except Exception as e:
        return f"Error: {str(e)}"

"""
# NOT ANYMORE LOL
async def ai_image_response(prompt):
    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: ai_client.models.generate_content(
                model="gemini-3.1-flash-image-preview",
                contents=[f"{prompt}"],
            ),
        )
        for part in response.parts: # type:ignore
            if part.inline_data is not None:
                image = part.as_image()

                img_bytes = io.BytesIO()
                image.save(img_bytes, format="PNG") # type:ignore
                img_bytes.seek(0)

                return img_bytes

        return None

    except Exception as e:
        return f"Error: {str(e)}"
"""

# ---------------- RSS CHECKERS ----------------


async def check_youtube():
    global last_youtube
    await bot.wait_until_ready()
    channel = bot.get_channel(YOUTUBE_VIDEOS_CHANNEL_ID)

    while not bot.is_closed():
        # Run the blocking feedparser in a separate thread
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(
            None, 
            functools.partial(feedparser.parse, YOUTUBE_RSS)
        )

        if feed.entries:
            latest = feed.entries.link
            if latest != last_youtube:
                last_youtube = latest
                embed = discord.Embed(
                    title="NEW YOUTUBE VIDEO 🔥",
                    description=latest,
                    color=0xFF0000, # YouTube Red
                )
                if channel:
                    await channel.send(embed=embed)

        await asyncio.sleep(300) # Check every 5 mins (don't spam or Nitter will ban you)


async def check_twitter():
    global last_twitter
    await bot.wait_until_ready()
    channel = bot.get_channel(TWITTER_POSTS_CHANNEL_ID)

    while not bot.is_closed():
        loop = asyncio.get_event_loop()
        feed = await loop.run_in_executor(
            None, 
            functools.partial(feedparser.parse, TWITTER_RSS)
        )

        if feed.entries:
            latest = feed.entries.link
            if latest != last_twitter:
                last_twitter = latest
                embed = discord.Embed(
                    title="NEW TWEET!",
                    description=latest,
                    color=0x1DA1F2,
                )
                if channel:
                    await channel.send(embed=embed)

        await asyncio.sleep(300)


# ---------------- EVENTS ----------------

@bot.event
async def on_ready():
    print("Discord Bot started...")

    bot.loop.create_task(check_twitter())
    bot.loop.create_task(check_youtube())


# ---------------- BASIC COMMANDS ----------------

@bot.command()
async def hi(ctx):
    await ctx.send("Hi, I'm nomnombaka!")


@bot.command()
async def help(ctx):
    view = HelpView()
    embed = view.get_embed("main")
    await ctx.send(embed=embed, view=view)

# ---------------- AI CHAT ----------------

@bot.command()
async def ai_chat(ctx, *, args):
    # Split by |
    if "|" in args:
        prompt, personality = map(str.strip, args.split("|", 1))
    else:
        prompt = args
        personality = None

    async with ctx.typing():
        reply = await ai_text_response(prompt=prompt, personality=personality)

    await ctx.send(reply)

"""
# NOT ANYMORE SORRY LOL
@bot.command()
async def ai_image(ctx, *, prompt):
    async with ctx.typing():
        result = await ai_image_response(prompt)

    if isinstance(result, str):
        return await ctx.send(result)

    if result is None:
        return await ctx.send("No image generated.")

    file = discord.File(fp=result, filename="generated.png")
    await ctx.send(file=file)

    result.close()
"""


# ---------------- MODERATION ----------------

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount+1)
    await ctx.send(f"Deleted {len(deleted)-1} previous messages", delete_after=1)

@bot.command()
@commands.has_permissions(manage_nicknames=True)
async def change_nickname(ctx, nickname, member : discord.Member):
        if member == ctx.author:
            return await ctx.send("You can't change your nickname yourself 💀")

        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send("I can't change nickname of this user.")

        if member.top_role >= ctx.author.top_role:
            return await ctx.send("You can't moderate this user.")

        try:
            await member.edit(nick=nick) # type: ignore
            await ctx.send(f"Changed nickname of {member.mention} to **{nickname}** 😈")
        except Exception as e:
            await ctx.send(f"Error: {e}")

@bot.command()
@commands.has_permissions(manage_nicknames=True)
async def reset_nickname(ctx, member : discord.Member):
        if member == ctx.author:
            return await ctx.send("You can't reset your nickname yourself 💀")

        if member.top_role >= ctx.guild.me.top_role:
            return await ctx.send("I can't reset nickname of this user.")

        if member.top_role >= ctx.author.top_role:
            return await ctx.send("You can't moderate this user.")

        try:
            await member.edit(nick=None) # type: ignore
            await ctx.send(f"Reset done for nickname of {member.mention} ✅")
        except Exception as e:
            await ctx.send(f"Error: {e}")

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):

    if member == ctx.author:
        return await ctx.send("You can't kick yourself 💀")

    if member.top_role >= ctx.guild.me.top_role:
        return await ctx.send("I can't kick this user.")

    if member.top_role >= ctx.author.top_role:
        return await ctx.send("You can't moderate this user.")

    try:
        await member.send(f"You were kicked from {ctx.guild.name}\nReason: {reason}")
        await member.kick(reason=reason)
        await ctx.send(f"Kicked {member}")
    except Exception as e:
        await ctx.send(f"Error: {e}")


@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason=None):

    if member == ctx.author:
        return await ctx.send("You can't ban yourself 💀")

    if member.top_role >= ctx.guild.me.top_role:
        return await ctx.send("I can't ban this user.")

    if member.top_role >= ctx.author.top_role:
        return await ctx.send("You can't moderate this user.")

    try:
        await member.send(f"You were banned from {ctx.guild.name}\nReason: {reason}")
        await member.ban(reason=reason)
        await ctx.send(f"Banned {member}")
    except Exception as e:
        await ctx.send(f"Error: {e}")


@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, *, user):

    banned_users = [entry async for entry in ctx.guild.bans()]

    for ban_entry in banned_users:
        if str(ban_entry.user) == user:
            await ctx.guild.unban(ban_entry.user)
            await ctx.send(f"Unbanned {ban_entry.user}")
            return

    await ctx.send("User not found.")


# ---------------- DM ----------------

@bot.command()
async def send_dm(ctx, user: discord.User, *, message: str):
    try:
        await user.send(message)
        await ctx.send(f"DM sent to {user.mention}!")
    except Exception as e:
        await ctx.send(f"Error: {e}")


# ---------------- TTS COMMAND ----------------

@bot.command()
async def say(ctx, *, text):
    mp3_fp = io.BytesIO()

    tts = gTTS(text)
    tts.write_to_fp(mp3_fp)
    mp3_fp.seek(0)

    file = discord.File(fp=mp3_fp, filename="voice.mp3")

    await ctx.send(file=file)

    file.close()
    mp3_fp.close()

# ----------------- MUSIC -----------------

@bot.command()
async def play_music(ctx, *, url : str):
        if not ctx.author.voice:
                await ctx.send("Join a music VC first!")

        channel = ctx.author.voice.channel
        vc = ctx.voice_client

        if vc is None:
                vc = await channel.connect()
        else:
                await vc.move_to(channel)

        if vc.is_playing():
                vc.stop()

        async with ctx.typing():
            try:
                audio_url, title = await get_audio_url(url)
            except Exception as e:
                return await ctx.send(f"Error fetching audio: {e}")

        source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS) # type: ignore
        vc.play(source)
        await ctx.send(f"Playing {title}!")

@bot.command()
async def stop_music(ctx):
        vc = ctx.voice_client
        if vc is None:
                return await ctx.send("I'm not in a voice channel")
        await vc.disconnect()
        await ctx.send("Stopped and left VC 👋")

# ---------------- RUN BOT ----------------

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

bot.run(BOT_TOKEN)
