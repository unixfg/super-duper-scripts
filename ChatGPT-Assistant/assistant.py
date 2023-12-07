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
DM_ROLE_ID = os.getenv('DM_ROLE_ID')
USERS_ROLE_ID = os.getenv('USERS_ROLE_ID')
BOT_CHANNEL_ID = os.getenv('BOT_CHANNEL_ID')

# Configure the root logger with a standard format
logging.basicConfig(level=logging.DEBUG, 
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
# This is a shortcut to set both guild_messages and dm_messages.
intents.messages = True
intents.guilds = True
bot = commands.Bot(command_prefix="/", intents=intents)

# RBAC Check
def get_user_role(member):
    """
    Retrieve the role of the user based on their member object.

    Args:
    member (discord.Member): The member object representing the user.

    Returns:
    str: The role of the user ("admin", "dm_user") or None if the role is not found.
    """
    # Check if the sender is an admin
    if str(member.id) == ADMIN_USER_ID:
        return "admin"

    # Check if the sender is a DM user
    for role in member.roles:
        if str(role.id) == DM_ROLE_ID:
            return "dm_user"
        
    # If there is a value in USERS_ROLE_ID, check if the sender is a user
    if USERS_ROLE_ID:
        for role in member.roles:
            if str(role.id) == USERS_ROLE_ID:
                return "user"

    # If neither, return None or "unknown"
    return "unknown"

# Retrieve or create a thread ID for a channel
def get_or_create_thread_id(channel_id):
    """
    Retrieve or create a thread ID for a channel.

    Args:
    channel_id (str): The channel ID in Discord.

    Returns:
    str: The thread ID in OpenAI.
    """
    cursor.execute("SELECT openai_thread_id FROM thread_mapping WHERE discord_channel_id = ?", (channel_id,))
    result = cursor.fetchone()
    
    if result:
        logger.info(f"Found existing thread ID for channel {channel_id}")
        return result[0]

    logger.info(f"Creating new thread for channel {channel_id}")
    thread = openai_client.beta.threads.create()
    thread_id = thread.id
    cursor.execute("INSERT INTO thread_mapping (discord_channel_id, openai_thread_id) VALUES (?, ?)", (channel_id, thread_id))
    conn.commit()
    return thread_id
  
async def poll_run_status_and_handle_response(thread_id, message, max_retries=1):
    """
    Polls the run status, handles the response based on the status, and retries if necessary.

    Args:
    thread_id (str): The thread ID in OpenAI.
    message (discord.Message): The original Discord message.
    max_retries (int): Maximum number of retries for failed runs.

    Returns:
    str or None: The response from OpenAI or None if no response is generated.
    """
    try:
        response = openai_client.beta.threads.runs.create(thread_id=thread_id, assistant_id=ASSISTANT_ID)
        run_id = response.id
        logger.debug(f"Run started: {run_id}")

        async with message.channel.typing():
            retries = 0
            while retries <= max_retries:
                run_status = openai_client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
                if run_status.status in ['completed', 'failed', 'expired', 'cancelled']:
                    break
                if run_status.status == 'requires_action':
                    openai_client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
                    logger.warning(f"Run {run_id} required action and was cancelled.")
                    return None
                await asyncio.sleep(1)

            if run_status.status != 'completed':
                logger.info(f"Run {run_id} ended with status: {run_status.status}")
                return None

            messages = openai_client.beta.threads.messages.list(thread_id=thread_id)
            latest_response = next((m for m in messages.data if m.role == 'assistant'), None)
            return latest_response.content[0].text.value if latest_response else None

    except Exception as e:
        logger.error(f"Error in OpenAI response generation: {e}")
        return None

# Bot commands
@bot.command(name='draw')
async def draw(ctx):
    """
    Draw an image with DALLE-3.

    Args:
    ctx (discord.ext.commands.Context): The context of the command.

    Returns:
    None
    """
    logger.info(f"Received draw command from {ctx.author}")
    await ctx.send("This command is not yet implemented.")

@bot.command(name='loglevel')
async def loglevel(ctx, level):
    """
    Change the log level of the bot.

    Args:
    ctx (discord.ext.commands.Context): The context of the command.
    level (str): The log level to set.

    Returns:
    None
    """
    logger.info(f"Received loglevel command from {ctx.author}")
    # Check if the sender is an admin
    if str(ctx.author.id) != ADMIN_USER_ID:
        await ctx.send("You are not authorized to use this command.")
        return
    if level in ["DEBUG", "INFO", "WARNING", "WARN", "FATAL", "ERROR"]:
        logger.setLevel(level)
        await ctx.send(f"Log level set to {level}")
    else:
        await ctx.send(f"Invalid log level: {level}")

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
    # Ignore messages from bots and self
    if message.author.bot:
        logger.debug("Ignoring bot message")
        return

    # Ignore empty messages
    if not message.content:
        logger.debug("Ignoring empty message")
        return

    logger.info(f"Received message from {message.author}: {message.content}")

    is_dm = message.channel.type == discord.ChannelType.private
    mentioned = bot.user.mentioned_in(message)
    user_role = get_user_role(message.author)

    logger.debug(f"Message is DM: {is_dm}, Bot mentioned: {mentioned}, User Role: {user_role}")

    # Only process DMs from privileged users
    if is_dm and (user_role == "admin" or user_role == "dm_user"):
        # Process the DM
        pass

    # Or process @tagged messages in a channel from privileged users
    elif not is_dm and mentioned and user_role != "unknown":
        # Process the mentioned message
        pass

    else:
        logger.info(f"Ignoring unauthorized message from {message.author} (ID: {message.author.id})")
        return

    thread_id = get_or_create_thread_id(str(message.channel.id))

    should_respond = (mentioned and not is_dm) or (is_dm and user_role in ["admin", "user"])
    logger.info(f"Should respond: {should_respond}")

    if should_respond:
        logger.info(f"Generating response for thread_id: {thread_id}")
        response = await poll_run_status_and_handle_response(thread_id, message)
        if response:
            await message.reply(response)
        else:
            logger.info("No response generated")
    else:
        logger.info("Conditions for generating response not met")

bot.run(DISCORD_TOKEN, log_handler=None, log_level=logging.DEBUG)
