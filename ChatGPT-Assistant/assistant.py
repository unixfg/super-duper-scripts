import os
import sqlite3
import discord
from discord.ext import commands
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()

# Initialize OpenAI client
openai.api_key = os.getenv('OPENAI_API_KEY')
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
client = commands.Bot(command_prefix="/", intents=intents)

# Bot configuration settings
trigger_keywords = ['help', 'question']  # Add more keywords as needed

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
    """Add a message to the OpenAI thread for maintaining context."""
    try:
        openai.ThreadMessage.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
            messages=[{"role": "user", "content": message_content}]
        )
    except Exception as e:
        print(f"Error adding message to OpenAI thread: {e}")

async def generate_openai_response(thread_id):
    """Generate a response from OpenAI based on the accumulated thread context."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        return response.choices[0].message['content']
    except Exception as e:
        print(f"Error generating OpenAI response: {e}")
        return "Sorry, I can't process that right now."

@client.event
async def on_ready():
    print('Bot is ready!')

@client.event
async def on_message(message):
    if message.author.bot or not message.content:
        return

    discord_channel_id = str(message.channel.id)
    openai_thread_id = get_openai_thread_id(discord_channel_id)

    if not openai_thread_id:
        # Create a new thread in OpenAI and store the mapping
        new_thread = openai.Thread.create(model="gpt-3.5-turbo", assistant_id=assistant_id)
        openai_thread_id = new_thread['id']
        set_openai_thread_id(discord_channel_id, openai_thread_id)

    # Add every message to the OpenAI thread
    await add_message_to_thread(openai_thread_id, message.content)

    # Check if the bot should respond
    should_respond = client.user.mentioned_in(message) or any(keyword in message.content.lower() for keyword in trigger_keywords)
    if should_respond:
        response = await generate_openai_response(openai_thread_id)
        await message.reply(response)

client.run(os.getenv('DISCORD_TOKEN'))
