# GroupMe-Discord
Bot to bridge a GroupMe group and a Discord channel

## Set-Up
The bot can be launched using `docker compose up`, which is likely the easiest way. You can also manually run a postgresql server and manually connect it to the Python bot script.

For GroupMe bot setup, you must [create a GroupMe bot](https://dev.groupme.com/tutorials/bots).

For Discord bot setup, you must [create a Discord application and bot](https://discord.com/developers/applications).

NOTE: GroupMe only allows a bot to exist in one group chat, so you must create a GroupMe bot per group chat you would like to bridge. However, you only ever need to create one Discord bot.
