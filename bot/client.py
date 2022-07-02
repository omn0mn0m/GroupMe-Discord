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

import asyncio
import asyncpg

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") # requires .env token
GROUPME_TOKEN = os.getenv("GROUPME_TOKEN") # requires .env token

POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")

# ==================================================
# Discord -> GroupMe
# ==================================================

discord_client = commands.Bot(command_prefix=commands.when_mentioned_or('g!'))

@discord_client.event
async def on_ready():
#    async with discord_client.pool.acquire() as db_connection:
#        for guild in bot.guilds:
#            await db_connection.execute('INSERT INTO guilds(id)')
    
    print('We have logged in as {0.user}'.format(discord_client))
    
    activity = discord.Activity(type=discord.ActivityType.playing, name=f"Anki")
    
    await discord_client.change_presence(status=discord.Status.idle, activity=activity)

@discord_client.command()
async def ping(context):
    await context.send('Pong!')

@discord_client.command()
@commands.has_permissions(administrator=True)
async def link(context, groupme_bot_id):
    req = requests.get(url='https://api.groupme.com/v3/bots?token={}'.format(GROUPME_TOKEN))

    groupme_bots = req.json()['response']
    groupme_bot_info = [bot for bot in groupme_bots if bot['bot_id'] == groupme_bot_id]

    if groupme_bot_info:
        groupme_bot_info = groupme_bot_info[0]

        async with discord_client.pool.acquire() as connection:
            await connection.execute('''
                INSERT INTO groupmes(groupme_id, groupme_bot_id, groupme_bot_name, discord_channel_id)
                VALUES($1, $2, $3, $4)
            ''', groupme_bot_info['group_id'], groupme_bot_id, groupme_bot_info['name'], context.channel.id)

        await context.send('Added bot to db: {} {} {} {} {}'.format(groupme_bot_info['group_id'], groupme_bot_id, groupme_bot_info['name'], context.guild.id, context.channel.id))
    else:
        await context.send('No GroupMe bot found with id: {}.'.format(groupme_bot_id))

@discord_client.command()
@commands.has_permissions(administrator=True)
async def unlink(context, groupme_bot_id):
    async with discord_client.pool.acquire() as connection:
        await connection.execute('''
        DELETE FROM groupmes
        WHERE groupme_bot_id=$1
        ''', groupme_bot_id)
        
        await context.send('Done!')

@discord_client.listen('on_message')
async def on_message(message):
    if message.author == discord_client.user or message.author.bot or ('g!' in message.content):
        return

    async with discord_client.pool.acquire() as connection:
        record = await connection.fetch('''
        SELECT groupme_bot_id FROM groupmes
        WHERE discord_channel_id=$1
        ''', message.channel.id)
        
        if record:
            groupme_bot_id = record[0]['groupme_bot_id']

            if str(message.channel.id):
                attachments = None
                groupme_message = '{}: {}'.format(message.author.display_name, message.clean_content)
        
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

                    print(parsed_response)

                    attachments = [{
                        'type': 'image',
                        'url': parsed_response['payload']['url'],
                    }]
            
                send_groupme_message(groupme_bot_id, groupme_message, attachments, '/')

def send_groupme_message(groupme_bot_id, message, attachments, callback):
    data = {
        'bot_id': groupme_bot_id,
        'text': message,
    }

    if attachments:
        data['attachments'] = attachments

    req = requests.post(url='https://api.groupme.com/v3/bots/post', json=data)

# ==================================================
# GroupMe -> Discord
# ==================================================
    
groupme_client = Quart(__name__)

@groupme_client.route('/callback/', methods=['POST'])
async def callback():
    data = await request.get_json()

    if data['name'] == 'Discord':
        return 'BOT'

    async with discord_client.pool.acquire() as connection:
        record = await connection.fetch('''
            SELECT discord_channel_id FROM groupmes
            WHERE groupme_id=$1
        ''', data['group_id'])

        if record:
            discord_channel_id = record[0]['discord_channel_id']

            file = None

            if len(data['attachments']):
                image = False
                
                if data['attachments'][0]['type'] == 'image' or data['attachments'][0]['type'] == 'video' or data['attachments'][0]['type'] == 'file':
                    file = data['attachments'][0]
                else:
                    print(data['attachments'][0]['type'])
                    
            await send_discord_message(discord_channel_id, "**{}**: {}".format(data['name'], data['text']), file, None)
        else:
            print('No record found...')

    return 'OK'

async def send_discord_message(discord_channel_id, message, file, callback):
    discord_channel = discord_client.get_channel(discord_channel_id)

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
async def main():
    credentials = {
        'user': POSTGRES_USER,
        'password': POSTGRES_PASSWORD,
        'database': POSTGRES_DATABASE,
        'host': POSTGRES_HOST,
    }

    discord_client.pool = await asyncpg.create_pool(**credentials)
    
    await discord_client.pool.execute('''
        CREATE TABLE IF NOT EXISTS groupmes(
            id SERIAL PRIMARY KEY,
            groupme_id text,
            groupme_bot_id text,
            groupme_bot_name text,
            discord_channel_id bigint
        )
    ''')

    try:
        await discord_client.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        await discord_client.pool.close()
        await discord_client.logout()

if __name__ == '__main__':
    discord_client.loop.create_task(groupme_client.run_task(host='0.0.0.0', port=8088))
    discord_client.loop.run_until_complete(main())
