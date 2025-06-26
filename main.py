import os
import disnake
from disnake.ext import commands
import sqlite3
from typing import Callable

intents = disnake.Intents.default()
intents.message_content = True

client = commands.Bot(intents=disnake.Intents.default())

db: sqlite3.Connection = sqlite3.connect("db.sqlite3")
cur: sqlite3.Cursor = db.cursor()

creator_id: int = int(os.environ.get("CREATOR_USER_ID"))

def create_user(id: int):
    cur.execute("INSERT INTO users VALUES (?, 0, 0)",(id,))
    db.commit()
def add_server(id: int, threshold: int,categoryid: int):
    cur.execute("INSERT INTO servers VALUES (?, ?, ?)",(id,threshold,categoryid))
    db.commit()
def server_exists(id):
    return cur.execute(f"SELECT EXISTS(SELECT 1 FROM servers WHERE serverid = ?)", (id,)).fetchone()[0] == 1
def user_exists(id):
    return cur.execute(f"SELECT EXISTS(SELECT 1 FROM users WHERE userid = ?)", (id,)).fetchone()[0] == 1
def set_server_fungus_threshold(id: int, threshold: int = 500):
    if not server_exists(id): return
    cur.execute("UPDATE servers SET fungus_xp = ? WHERE serverid = ?",(threshold,id))
    db.commit()

def increase_user_value(id: int, increment: int, column: str):
    if not user_exists(id): return
    cur.execute(f"UPDATE users SET {column} = {column} + ? WHERE userid = ?",(id,increment))
    db.commit()
def add_user_games(id: int, increment: int = 1): increase_user_value(id,increment,"played_games")
def add_user_xp(id: int, increment: int = 1): increase_user_value(id,increment,"xp")
        
def is_admin(user: disnake.Member):
    return user.id == creator_id or user.guild_permissions.administrator

def get_needed_server_xp(id: int):
    return r[0] if (r:=cur.execute("SELECT fungus_xp FROM servers WHERE serverid = ?",(id,)).fetchone()) is not None else None
def get_user_xp(id: int):
    return r[0] if (r:=cur.execute("SELECT xp FROM users WHERE userid = ?",(id,)).fetchone()) is not None else None

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}. Creator ID: {creator_id}')


@client.slash_command(name="hello",description="Test whether the bot is up")
async def hello_command(interaction: disnake.ApplicationCommandInteraction):
    await interaction.response.send_message(f"Hello world! (Your user id is {interaction.author.id})",ephemeral=True)

@client.slash_command(name="setthreshold",description="Set a threshold for the required XP level to be considered a fungus")
async def set_threshold(interaction: disnake.ApplicationCommandInteraction, xp: int = 500):
    if not is_admin(interaction.author):
        await interaction.response.send_message("You can't do that.",ephemeral=True)
        return
    set_server_fungus_threshold(interaction.guild.id,xp)
    await interaction.response.send_message(f"New threshold set! Now a player needs to have {xp} XP to be a fungus.",
                                            ephemeral=True)
    
@client.slash_command(name="createforest",description="Creates a new forest (only available to fungi)")
async def create_forest(interaction: disnake.ApplicationCommandInteraction, name: str):
    userxp = get_user_xp(interaction.user.id)
    needed = get_needed_server_xp(interaction.guild.id)
    if needed is None:
        await interaction.response.send_message("This server is not registered yet. An admin can register the server using /registerserver.",ephemeral=True)
        return
    if userxp is None:
        create_user(interaction.author.id)
        await interaction.response.send_message(f"You are not a fungus. You have 0 XP but {needed[0]} is required.",ephemeral=True)
        return
    if userxp[0] < needed[0]:
        await interaction.response.send_message(f"You are not a fungus. You have {userxp[0]} XP but {needed[0]} XP is required.",ephemeral=True)
        return
    await interaction.response.send_message(f"Creating a new forest with the name of {name}...")

@client.slash_command(name="registerserver",description="Register the server to allow creating forests")
async def register_server(interaction: disnake.ApplicationCommandInteraction,
                          category: disnake.CategoryChannel = commands.Param(name="category",
                        description="The category which the bot will use to create channels")):
    if not is_admin(interaction.author):
        await interaction.response.send_message("You can't do that.",ephemeral=True)
        return
    add_server(interaction.guild.id,500,category.id)
    await interaction.response.send_message(f"Added this server to the database. Now the bot will use the {str(category)} category to create forests.")

client.run(os.environ.get("DISCORD_TOKEN"))