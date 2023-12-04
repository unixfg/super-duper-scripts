import os
import asyncio
import logging
import sqlite3
import discord
from discord.ext import commands
from dotenv import load_dotenv
import openai

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Retrieve the assistant ID
assistant_id = os.getenv('ASSISTANT_ID')

# Initialize OpenAI client
openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

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
    """Create a run for the given thread and retrieve the response when ready."""
    try:
        # Create a run
        run = openai_client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)
        run_id = run.id  # Use dot notation to access the id

        # Poll for the run's completion
        while True:
            run_status = openai_client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
            if run_status.status == 'completed':  # Use dot notation
                break
            await asyncio.sleep(2)  # Sleep for a short period before polling again

        # Retrieve the thread messages
        thread_messages = openai_client.beta.threads.messages.list(thread_id)

        # Find the latest assistant's response
        response_messages = [msg for msg in reversed(thread_messages.data) if msg.role == 'assistant']

        # Extract and concatenate text from each message content
        response_text = ""
        for msg in response_messages:
            for content in msg.content:
                if content.type == 'text':
                    response_text += content.text.value + "\n"

        return response_text.strip() if response_text else None
    except Exception as e:
        logging.error(f"Error in run or retrieving messages: {e}")
        return None

@bot.event
async def on_ready():
    print('Bot is ready!')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Check if the message is a DM
    is_dm = isinstance(message.channel, discord.DMChannel)

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
