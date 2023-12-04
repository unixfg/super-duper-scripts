import os
import asyncio
import logging
import sqlite3
import discord
from discord.ext import commands
from dotenv import load_dotenv
import openai
import time

ADMIN_ROLE_NAME = "Nerds"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Initialize OpenAI client
openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
assistant_id = os.getenv('ASSISTANT_ID')

# Database setup
conn = sqlite3.connect('bot_data.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS thread_mapping (discord_channel_id TEXT PRIMARY KEY, openai_thread_id TEXT)''')
conn.commit()

# Discord Client
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
bot = commands.Bot(command_prefix="/", intents=intents)

def get_openai_thread_id(discord_channel_id):
    """Retrieve OpenAI thread ID for a given Discord channel."""
    cursor.execute("SELECT openai_thread_id FROM thread_mapping WHERE discord_channel_id = ?", (discord_channel_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def set_openai_thread_id(discord_channel_id, openai_thread_id):
    """Set or update the OpenAI thread ID for a given Discord channel."""
    cursor.execute("INSERT OR REPLACE INTO thread_mapping (discord_channel_id, openai_thread_id) VALUES (?, ?)", (discord_channel_id, openai_thread_id))
    conn.commit()

async def add_message_to_thread(thread_id, message_content):
    """Add a message to an existing OpenAI thread."""
    try:
        # Add message to the existing thread
        thread_message = openai_client.beta.threads.messages.create(
            thread_id,
            role="user",
            content=message_content
        )
    except Exception as e:
        logging.error(f"Error adding message to OpenAI thread: {e}")


async def create_run_and_get_response(thread_id):
    try:
        # Create a run
        logging.info(f"Creating a run for thread ID: {thread_id}")
        run = openai_client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)
        run_id = run.id

        # Initialize polling variables
        timeout = 60  # Total timeout in seconds
        start_time = time.time()
        interval = 1  # Initial polling interval in seconds
        max_interval = 5  # Maximum polling interval

        while True:
            current_time = time.time()
            if current_time - start_time > timeout:
                # Cancel the run if it takes too long
                logging.info(f"Run {run_id} timed out. Canceling...")
                openai_client.beta.threads.runs.cancel(thread_id=thread_id, run_id=run_id)
                break

            run_status = openai_client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
            if run_status.status == 'completed':
                logging.info(f"Run {run_id} completed")
                break

            await asyncio.sleep(interval)
            interval = min(max_interval, interval + 1)  # Increment the interval

        # Retrieve the thread messages
        thread_messages = openai_client.beta.threads.messages.list(thread_id)
        latest_response = next((msg for msg in thread_messages.data if msg.role == 'assistant'), None)
        
        # Parse the response
        if latest_response:
            return parse_response(latest_response)
        return None
    except Exception as e:
        logging.error(f"Error in run or retrieving messages: {e}")
        # Attempt to fetch the message even in case of error
        thread_messages = openai_client.beta.threads.messages.list(thread_id)
        latest_response = next((msg for msg in thread_messages.data if msg.role == 'assistant'), None)
        return parse_response(latest_response) if latest_response else None

def parse_response(latest_response):
    """Parse the latest response to extract text."""
    response_text = ""
    for content in latest_response.content:
        if content.type == 'text':
            response_text += content.text.value + "\n"
    return response_text.strip()

async def is_user_admin_in_any_server(user):
    """Check if the user is an admin in any server the bot is in."""
    for guild in bot.guilds:
        member = guild.get_member(user.id)
        if member and any(role.permissions.administrator for role in member.roles):
            return True
    return False

async def is_user_admin_in_server(user, guild):
    """Check if the user is an admin in the specified server."""
    member = guild.get_member(user.id)
    return member and any(role.permissions.administrator for role in member.roles)

@bot.event
async def on_ready():
    print('Bot is ready!')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Check if the message is a DM
    is_dm = isinstance(message.channel, discord.DMChannel)

    if is_dm:
        # Check if the sender is an admin in any server
        if not await is_user_admin_in_any_server(message.author):
            logging.info(f"Ignoring DM from non-admin user: {message.author}")
            return  # Ignore DMs from non-admins
    else:
        # In server channels, only respond to mentions if the user is an admin
        if bot.user.mentioned_in(message):
            if not await is_user_admin_in_server(message.author, message.guild):
                logging.info(f"Ignoring mention from non-admin user: {message.author} in server: {message.guild.name}")
                return  # Ignore mentions from non-admins

    discord_channel_id = str(message.channel.id)
    openai_thread_id = get_openai_thread_id(discord_channel_id)

    if not openai_thread_id:
        new_thread = openai_client.beta.threads.create()
        openai_thread_id = new_thread.id
        set_openai_thread_id(discord_channel_id, openai_thread_id)

    # Add every message to the OpenAI thread
    await add_message_to_thread(openai_thread_id, message.content)

    # Define conditions for generating a response
    should_respond = is_dm or bot.user.mentioned_in(message)
    if should_respond:
        response = await create_run_and_get_response(openai_thread_id)
        if response:
            # Check if the response exceeds Discord's character limit
            max_length = 2000
            if len(response) > max_length:
                # Split the response into multiple messages if it's too long
                for i in range(0, len(response), max_length):
                    await message.reply(response[i:i + max_length])
            else:
                await message.reply(response)

bot.run(os.getenv('DISCORD_TOKEN'))
