import os
import asyncio
import logging
import sqlite3
import discord
from discord.ext import commands
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()

# Environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
ASSISTANT_ID = os.getenv('ASSISTANT_ID')
ADMIN_USER_ID = os.getenv('ADMIN_USER_ID')
BOT_CHANNEL_ID = os.getenv('BOT_CHANNEL_ID')

# Logger setup
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)

# OpenAI client initialization
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Database setup
conn = sqlite3.connect('bot_data.db')
cursor = conn.cursor()

# Discord bot setup
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.dm_messages = True
bot = commands.Bot(command_prefix="/", intents=intents)

# RBAC Check
def is_admin(user):
    return str(user.id) == ADMIN_USER_ID

# Bot commands
@bot.command()
async def toggledebug(ctx):
    if not is_admin(ctx.author):
        await ctx.send("You do not have permission to use this command.")
        return

    if logger.level == logging.INFO:
        logger.setLevel(logging.DEBUG)
        await ctx.send("Debug mode enabled.")
    else:
        logger.setLevel(logging.INFO)
        await ctx.send("Debug mode disabled.")

# Retrieve or create a thread ID for a channel
def get_or_create_thread_id(channel_id):
    cursor.execute("SELECT openai_thread_id FROM thread_mapping WHERE discord_channel_id = ?", (channel_id,))
    result = cursor.fetchone()
    
    if result:
        return result[0]

    thread = openai_client.beta.threads.create()
    thread_id = thread.id
    cursor.execute("INSERT INTO thread_mapping (discord_channel_id, openai_thread_id) VALUES (?, ?)", (channel_id, thread_id))
    conn.commit()
    return thread_id

# Bot event handlers
@bot.event
async def on_ready():
    logger.info('Bot is ready!')
    if 'BOT_CHANNEL_ID' in locals():
        channel = bot.get_channel(int(BOT_CHANNEL_ID))
        if channel:
            await channel.send("ChadGPT is Online.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not is_admin(message.author) and not message.content.startswith('/'):
        return

    thread_id = get_or_create_thread_id(str(message.channel.id))

    # Generate and send response
    try:
        response = openai_client.beta.threads.runs.create(thread_id=thread_id, assistant_id=ASSISTANT_ID)
        run_id = response.id

        # Poll for run completion
        for _ in range(60):
            run_status = openai_client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
            if run_status.status == 'completed':
                break
            await asyncio.sleep(1)

        # Handle incomplete run
        if run_status.status != 'completed':
            openai_client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
            logger.info(f"Thread {thread_id}, run {run_id} timed out and was cancelled.")

        # Retrieve and send the response
        messages = openai_client.beta.threads.messages.list(thread_id=thread_id)
        latest_response = next((m for m in messages.data if m.role == 'assistant'), None)

        if latest_response:
            await message.reply(latest_response.content[0].text.value)
    except Exception as e:
        logger.error(f"Error in OpenAI response generation: {e}")

    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
