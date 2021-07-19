import discord
from discord.ext import commands
from discord.ext.commands import Context

import io
import json
import os
from dotenv import load_dotenv

import requests

from quart import Quart

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
GROUPME_BOT_ID = os.getenv("GROUPME_BOT_ID")
GROUPME_TOKEN = os.getenv("GROUPME_TOKEN")

# ==================================================
# Discord -> GroupMe
# ==================================================

discord_client = commands.Bot(command_prefix=commands.when_mentioned_or('g!'))

@discord_client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(discord_client))
    
    activity = discord.Activity(type=discord.ActivityType.playing, name=f"PBLs")
    
    await discord_client.change_presence(status=discord.Status.idle, activity=activity)

@discord_client.listen('on_message')
async def on_message(message):
    if message.author == discord_client.user or message.author.bot:
        return

    if str(message.channel.id) == str(DISCORD_CHANNEL_ID):
        attachments = None
        groupme_message = '{}: {}'.format(message.author.display_name, message.content)

        if len(message.attachments):
            attachment = message.attachments[0]
            
            fp = io.BytesIO()
            bytes_written = await attachment.save(fp)

            headers = {
                'X-Access-Token': GROUPME_TOKEN,
            }

            files = {
                'file': fp,
            }

            req = requests.post('https://image.groupme.com/pictures', headers=headers, files=files)
            parsed_response = json.loads(req.text)

            attachments = [{
                'type': 'image',
                'url': parsed_response['payload']['url'],
            }]

            groupme_message = '{} sent an image:'.format(message.author.display_name)
       
        send_groupme_message(groupme_message, attachments, '/')

def send_groupme_message(message, attachments, callback):
    data = {
        'bot_id': GROUPME_BOT_ID,
        'text': message,
    }

    if attachments:
        data['attachments'] = attachments

    req = requests.post(url='https://api.groupme.com/v3/bots/post', json=data)

# ==================================================
# GroupMe -> Discord
# ==================================================
    
groupme_client = Quart(__name__)

@groupme_client.route('/callback', methods=['POST'])
async def callback():
    print(request.body)

# ==================================================
# Main Logic
# ==================================================
if __name__ == '__main__':
    discord_client.loop.create_task(groupme_client.run_task(port=8089))
    discord_client.run(DISCORD_TOKEN)
