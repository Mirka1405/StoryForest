import os
import disnake
from disnake.ext import commands

intents = disnake.Intents.default()
intents.message_content = True

# client = disnake.Client(intents=intents)
client = commands.Bot(intents=disnake.Intents.default())

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

# @client.event
# async def on_message(message):
#     if message.author == client.user:
#         return

#     if message.content.startswith('$hello'):
#         await message.channel.send('Hello!')

@client.slash_command(name="hello",description="Test whether the bot is up")
async def hello_command(interaction):
    await interaction.response.send_message("Hello world!")


client.run(os.environ.get("DISCORD_TOKEN"))