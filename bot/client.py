import discord
from discord.ext import commands
import discord
from discord.ext.commands import Context

import io
import aiohttp
import json
import os
from dotenv import load_dotenv

import requests

from quart import Quart
from quart import request

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
GROUPME_BOT_ID = os.getenv("GROUPME_BOT_ID")
GROUPME_TOKEN = os.getenv("GROUPME_TOKEN")
GROUPME_BOT_NAME = os.getenv("GROUPME_BOT_NAME")

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
    data = await request.get_json()

    if data['name'] == GROUPME_BOT_NAME:
        return 'BOT'

    file = None

    if len(data['attachments']):
        image = False

        if data['attachments'][0]['type'] == 'image' or data['attachments'][0]['type'] == 'video' or data['attachments'][0]['type'] == 'file':
            file = data['attachments'][0]
        else:
            print(data['attachments'][0]['type'])

    await send_discord_message("**{}**: {}".format(data['name'], data['text']), file, None)

    return 'OK'

async def send_discord_message(message, file, callback):
    discord_channel = discord_client.get_channel(DISCORD_CHANNEL_ID)

    if file:
        async with aiohttp.ClientSession() as session:
            async with session.get(file['url']) as response:
                if response.status != 200:
                    return

                httpFile = io.BytesIO(await response.read())

                if file['type'] == 'image':
                    fileExtension = '.png'
                elif file['type'] == 'video':
                    fileExtension = '.mkv'

                await discord_channel.send(message, file=discord.File(httpFile, 'groupme_file' + fileExtension))
    else:
        await discord_channel.send(message)


# ==================================================
# Main Logic
# ==================================================
if __name__ == '__main__':
    discord_client.loop.create_task(groupme_client.run_task(host='0.0.0.0', port=8089))
    discord_client.run(DISCORD_TOKEN)
