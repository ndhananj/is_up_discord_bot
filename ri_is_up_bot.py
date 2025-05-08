"""
Discord Website Monitor Bot
Checks if a website is up by monitoring a specific image and reports to a private channel
"""
import os
import time
import asyncio
import datetime
from dotenv import load_dotenv
import discord
from discord.ext import tasks
import aiohttp

# Load environment variables
load_dotenv()

# Configuration
CONFIG = {
    # The URL to check
    "check_url": "https://resilientinterface.com/resources/images/info-hub.png",
    
    # Channel ID where the bot will report status
    "status_channel_id": int(os.getenv("STATUS_CHANNEL_ID", "YOUR_PRIVATE_CHANNEL_ID")),
    
    # User ID to send direct messages to
    "user_id": int(os.getenv("USER_ID", "YOUR_DISCORD_USER_ID")),
    
    # How often to check the website (in seconds)
    # Default is every hour
    "check_interval": 3600,
    
    # Display name for the website being monitored
    "website_name": "ResilientInterface",
    
    # Website home URL for reporting
    "website_home_url": "https://resilientinterface.com",
    
    # Log additional information to console
    "debug": True
}

# Status tracking
last_status = None
consecutive_failures = 0
MAX_CONSECUTIVE_FAILURES = 3  # Number of failures before alerting

# Set up Discord bot with intents
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
command_tree = discord.app_commands.CommandTree(bot)

@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord"""
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')
    print(f"Website monitor started for {CONFIG['website_name']}")
    print(f"Checking {CONFIG['check_url']} every {CONFIG['check_interval']} seconds")
    
    # Start the monitoring task
    check_website.start()

@tasks.loop(seconds=CONFIG["check_interval"])
async def check_website():
    """Check if the website is up on a regular interval"""
    global last_status, consecutive_failures
    
    start_time = time.time()
    status = {
        "online": False,
        "response_time": 0,
        "message": "",
        "timestamp": datetime.datetime.now()
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Use aiohttp to make a GET request to the image URL
            async with session.get(CONFIG["check_url"], timeout=10) as response:
                # Calculate response time
                status["response_time"] = int((time.time() - start_time) * 1000)  # Convert to ms
                
                # Check if response is successful and contains image data
                content_type = response.headers.get('content-type', '')
                if response.status == 200 and content_type.startswith('image/'):
                    status["online"] = True
                    status["message"] = f"{CONFIG['website_name']} is online. Response time: {status['response_time']}ms"
                    consecutive_failures = 0
                else:
                    status["online"] = False
                    status["message"] = f"{CONFIG['website_name']} returned status {response.status} but invalid content type: {content_type}"
                    consecutive_failures += 1
    
    except Exception as e:
        status["online"] = False
        status["response_time"] = int((time.time() - start_time) * 1000)  # Convert to ms
        status["message"] = f"{CONFIG['website_name']} is down. Error: {str(e)}"
        consecutive_failures += 1
        
        if CONFIG["debug"]:
            print(f"Error checking website: {str(e)}")
    
    if CONFIG["debug"]:
        print(status["message"])
    
    # Report status change or after consecutive failures
    if (last_status is None or 
            last_status["online"] != status["online"] or 
            (consecutive_failures >= MAX_CONSECUTIVE_FAILURES and not status["online"])):
        await report_status(status)
    
    last_status = status

async def report_status(status):
    """Report status to Discord channel and user"""
    status_channel = bot.get_channel(CONFIG["status_channel_id"])
    user = await bot.fetch_user(CONFIG["user_id"])
    
    if not status_channel:
        print(f"Cannot find channel with ID {CONFIG['status_channel_id']}")
        return
    
    if not user:
        print(f"Cannot find user with ID {CONFIG['user_id']}")
        return
    
    # Create embed for Discord message
    embed = discord.Embed(
        title=f"{CONFIG['website_name']} Status Update",
        url=CONFIG['website_home_url'],
        description=status["message"],
        color=discord.Color.green() if status["online"] else discord.Color.red(),
        timestamp=status["timestamp"]
    )
    
    embed.add_field(name="Status", value="✅ Online" if status["online"] else "❌ Offline")
    embed.add_field(name="Response Time", value=f"{status['response_time']}ms")
    embed.add_field(name="Checked URL", value=CONFIG["check_url"])
    embed.set_footer(text="Website Monitor Bot")
    
    # Send to channel
    await status_channel.send(embed=embed)
    
    # Send to user
    try:
        await user.send(embed=embed)
    except discord.Forbidden:
        print(f"Cannot send DM to user {user.name}. They may have DMs disabled.")
    except Exception as e:
        print(f"Error sending DM to user: {str(e)}")

@check_website.before_loop
async def before_check_website():
    """Wait until the bot is ready before starting the task"""
    await bot.wait_until_ready()

# Handle errors
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"Discord client error in {event}: {args} {kwargs}")

# Start the bot
if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))