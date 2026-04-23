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
from typing import Any
from discord.ui import View, button
import functools
import base64

# 🔥 NEW: Lavalink
import wavelink

# LOAD ENV VARIABLES
load_dotenv()

# CONSTANTS
TWITTER_POSTS_CHANNEL_ID = 1495834413442011318
TWITTER_RSS = "https://nitter.net/r1ktx/rss"

YOUTUBE_VIDEOS_CHANNEL_ID = 1496108672768540734
YOUTUBE_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id=UCQJLTQrzErVvASGrVInfTAA"

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
                    "`!purge <amount>`\n"
                    "`!change_nickname <user> <nick>`\n"
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

# ---------------- LAVALINK SETUP ----------------

class MyBot(commands.Bot):
    async def setup_hook(self):
        node = wavelink.Node(
            uri="http://127.0.0.1:2333",
            password="youshallnotpass"
        )

        await wavelink.Pool.connect(nodes=[node], client=self, cache_capacity=100)

# replace bot instance
bot = MyBot(command_prefix="!", intents=intents, help_command=None)

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

# ---------------- RSS CHECKERS (UNCHANGED) ----------------

async def check_youtube():
    global last_youtube
    await bot.wait_until_ready()
    channel = bot.get_channel(YOUTUBE_VIDEOS_CHANNEL_ID)

    while not bot.is_closed():
        try:
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
                        color=0xFF0000,
                    )
                    if channel:
                        await channel.send(embed=embed)
        except Exception as e:
            print(f"RSS error: {e}")

        await asyncio.sleep(300)

async def check_twitter():
    global last_twitter
    await bot.wait_until_ready()
    channel = bot.get_channel(TWITTER_POSTS_CHANNEL_ID)

    while not bot.is_closed():
        try:
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
        except Exception as e:
            print(f"RSS error: {e}")

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
    if "|" in args:
        prompt, personality = map(str.strip, args.split("|", 1))
    else:
        prompt = args
        personality = None

    async with ctx.typing():
        reply = await ai_text_response(prompt=prompt, personality=personality)

    await ctx.send(reply)

# ---------------- MODERATION (UNCHANGED) ----------------
# (I am keeping ALL your mod commands exactly as-is to avoid breaking anything)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    deleted = await ctx.channel.purge(limit=amount+1)
    await ctx.send(f"Deleted {len(deleted)-1} previous messages", delete_after=1)

# (rest of moderation code unchanged — omitted here ONLY for brevity, but keep in your file exactly)

# ---------------- DM / TTS (UNCHANGED) ----------------

@bot.command()
async def send_dm(ctx, user: discord.User, *, message: str):
    try:
        await user.send(message)
        await ctx.send(f"DM sent to {user.mention}!")
    except Exception as e:
        await ctx.send(f"Error: {e}")

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

# ---------------- 🎵 MUSIC (LAVALINK VERSION) ----------------

@bot.command()
async def play_music(ctx, *, query: str):
    if not ctx.author.voice:
        return await ctx.send("Join a music VC first!")

    player: wavelink.Player = ctx.voice_client

    if player is None:
        player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
    else:
        await player.move_to(ctx.author.voice.channel)

    tracks = await wavelink.YouTubeTrack.search(query)
    if not tracks:
        return await ctx.send("No results found.")

    track = tracks[0]

    await player.play(track)
    await ctx.send(f"Playing {track.title} 🎶")

@bot.command()
async def stop_music(ctx):
    player: wavelink.Player = ctx.voice_client

    if not player:
        return await ctx.send("I'm not in a voice channel")

    await player.disconnect()
    await ctx.send("Stopped and left VC 👋")

# ---------------- RUN BOT ----------------

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found")

bot.run(BOT_TOKEN)
