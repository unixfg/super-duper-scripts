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
USERS_ROLE_ID = os.getenv('USERS_ROLE_ID')
BOT_CHANNEL_ID = os.getenv('BOT_CHANNEL_ID')

# Configure the root logger with a standard format
logging.basicConfig(level=logging.WARN, 
                    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

# Create and configure your bot's logger
logger = logging.getLogger('bot')

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
def get_user_role(member):
    # Check if the member is an admin
    if str(member.id) == ADMIN_USER_ID:
        return "admin"

    # Check if the member has the specific role
    for role in member.roles:
        if str(role.id) == USERS_ROLE_ID:
            return "user"

    # If neither, return None or "unknown"
    return "unknown"

# Retrieve or create a thread ID for a channel
def get_or_create_thread_id(channel_id):
    cursor.execute("SELECT openai_thread_id FROM thread_mapping WHERE discord_channel_id = ?", (channel_id,))
    result = cursor.fetchone()
    
    if result:
        logger.debug(f"Found existing thread ID for channel {channel_id}")
        return result[0]

    logger.debug(f"Creating new thread for channel {channel_id}")
    thread = openai_client.beta.threads.create()
    thread_id = thread.id
    cursor.execute("INSERT INTO thread_mapping (discord_channel_id, openai_thread_id) VALUES (?, ?)", (channel_id, thread_id))
    conn.commit()
    return thread_id

# Add message to thread
async def add_message_to_thread(thread_id, message_content):
    try:
        openai_client.beta.threads.messages.create(thread_id, role="user", content=message_content)
    except Exception as e:
        logger.error(f"Error adding message to OpenAI thread: {e}")

# Generate response from OpenAI
async def generate_response_from_openai(thread_id, message):
    try:
        logger.debug(f"Starting run for thread_id: {thread_id}")
        response = openai_client.beta.threads.runs.create(thread_id=thread_id, assistant_id=ASSISTANT_ID)
        run_id = response.id
        logger.debug(f"Run started: {run_id}")

        # Start typing notification
        async with message.channel.typing():
        # Poll for run completion
            for _ in range(60):
                run_status = openai_client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
                if run_status.status == 'completed':
                    logger.debug(f"Run completed: {run_id}")
                    break
            await asyncio.sleep(1)

        # Handle incomplete run
        if run_status.status != 'completed':
            openai_client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
            logger.warning(f"Run {run_id} timed out and was cancelled.")

        messages = openai_client.beta.threads.messages.list(thread_id=thread_id)
        latest_response = next((m for m in messages.data if m.role == 'assistant'), None)

        return latest_response.content[0].text.value if latest_response else None
    except Exception as e:
        logger.error(f"Error in OpenAI response generation: {e}")
        return None

# Bot event handlers
@bot.event
async def on_ready():
    logger.info('Bot is ready!')
    if BOT_CHANNEL_ID:
        channel = bot.get_channel(int(BOT_CHANNEL_ID))
        if channel:
            await channel.send("ChadGPT is Online.")

@bot.event
async def on_message(message):
    if message.author.bot:
        logger.debug("Ignoring bot message")
        return

    logger.debug(f"Received message from {message.author}: {message.content}")

    is_dm = message.channel.type == discord.ChannelType.private
    mentioned = bot.user.mentioned_in(message)
    user_role = get_user_role(message.author)

    logger.debug(f"Message is DM: {is_dm}, Bot mentioned: {mentioned}, User Role: {user_role}")

    if is_dm and user_role != "admin":
        logger.debug(f"Ignoring DM from non-admin user: {message.author} (ID: {message.author.id})")
        return

    # Additional check for @tagged messages in a channel
    if not is_dm and "@" in message.content and user_role not in ["admin", "user"]:
        logger.debug("Ignoring @tagged message from non-privileged user")
        return

    thread_id = get_or_create_thread_id(str(message.channel.id))
    await add_message_to_thread(thread_id, message.content)

    should_respond = (mentioned and not is_dm) or (is_dm and user_role in ["admin", "user"])
    logger.debug(f"Should respond: {should_respond}")

    if should_respond:
        logger.debug(f"Generating response for thread_id: {thread_id}")
        response = await generate_response_from_openai(thread_id, message)
        if response:
            await message.reply(response)
        else:
            logger.debug("No response generated")
    else:
        logger.debug("Conditions for generating response not met")

    await bot.process_commands(message)

bot.run(DISCORD_TOKEN, log_handler=None, log_level=logging.DEBUG)
