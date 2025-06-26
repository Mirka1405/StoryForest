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
    cur.execute("INSERT INTO users VALUES (?, 0, 0, 0)",(id,))
    db.commit()
def add_server(id: int, threshold: int,categoryid: int,archivecategoryid: int):
    cur.execute("INSERT INTO servers VALUES (?, ?, ?, ?)",(id,threshold,categoryid,archivecategoryid))
    db.commit()
def remove_server(id: int):
    cur.execute("DELETE FROM servers WHERE serverid = ?",(id,))
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
    cur.execute(f"UPDATE users SET {column} = {column} + ? WHERE userid = ?",(increment,id))
    db.commit()
def add_user_games(id: int, increment: int = 1): increase_user_value(id,increment,"played_games")
def add_user_xp(id: int, increment: int = 1): increase_user_value(id,increment,"xp")
        
def is_admin(user: disnake.Member):
    return user.id == creator_id or user.guild_permissions.administrator

def get_needed_server_xp(id: int):
    return r[0] if (r:=cur.execute("SELECT fungus_xp FROM servers WHERE serverid = ?",(id,)).fetchone()) is not None else None
def get_server_forest_category(id: int):
    return r[0] if (r:=cur.execute("SELECT categoryid FROM servers WHERE serverid = ?",(id,)).fetchone()) is not None else None
def get_server_archive_category(id: int):
    return r[0] if (r:=cur.execute("SELECT archivecategoryid FROM servers WHERE serverid = ?",(id,)).fetchone()) is not None else None
def get_user_xp(id: int):
    return r[0] if (r:=cur.execute("SELECT xp FROM users WHERE userid = ?",(id,)).fetchone()) is not None else None
def get_user_games(id: int):
    return r[0] if (r:=cur.execute("SELECT played_games FROM users WHERE userid = ?",(id,)).fetchone()) is not None else None


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
        await interaction.response.send_message(f"You are not a fungus. You have 0 XP but {needed} is required.",ephemeral=True)
        return
    if userxp < needed:
        await interaction.response.send_message(f"You are not a fungus. You have {userxp} XP but {needed} XP is required.",ephemeral=True)
        return
    await interaction.response.send_message(f"Creating a new forest with the name of {name}...",ephemeral=True)
    channel = await interaction.guild.create_text_channel(
        name=f"{name}-by-{interaction.author.name}",
        category=client.get_channel(get_server_forest_category(interaction.guild.id)),
        topic=str(interaction.user.id)
    )
    await interaction.followup.send(
        f"Created a new forest: {channel.mention}. Use /join to become a tree in this forest.\nFungus: {interaction.author.mention}"
    )


@client.slash_command(name="registerserver",description="Register the server to allow creating forests")
async def register_server(interaction: disnake.ApplicationCommandInteraction,
                          forestcategory: disnake.CategoryChannel = commands.Param(name="forest_category",
                        description="The category which the bot will use to create channels"),
                        archivecategory: disnake.CategoryChannel = commands.Param(name="archive_category",
                        description="The category which be used for storing archived forests")
                        ):
    if server_exists(interaction.guild.id):
        remove_server(interaction.guild.id)
    if not is_admin(interaction.author):
        await interaction.response.send_message("You can't do that.",ephemeral=True)
        return
    add_server(interaction.guild.id,500,forestcategory.id,archivecategory.id)
    await interaction.response.send_message(f"Added this server to the database. Now the bot will use the {forestcategory.mention} category to create forests. Archived forests will be stored in {archivecategory.mention}.")


@client.slash_command(name="stats",description="See user stats")
async def stats(interaction: disnake.ApplicationCommandInteraction,
                user: disnake.Member = commands.Param(
                    default=None, 
                    description="The user to get info about (defaults to you)"
                )):
    user = user or interaction.author
    if not user_exists(user.id):
        await interaction.response.send_message("This user hasn't participated in any forests yet!",ephemeral=True)
        return
    await interaction.response.send_message(f"{user.mention}:\nXP: {get_user_xp(user.id)}/{get_needed_server_xp(interaction.guild.id)}\nTotal games played: {get_user_games(user.id)}",ephemeral=True)


@client.slash_command(name="join",description="Join a forest (create a private thread for you and the fungus)")
async def join(interaction: disnake.ApplicationCommandInteraction):
    category = get_server_forest_category(interaction.guild.id)
    if interaction.channel.category.id != category:
        await interaction.response.send_message(f"This is not a forest channel. Only channels in {client.get_channel(category).mention} are considered forests.",ephemeral=True)
        return
    if str(interaction.author.id) == interaction.channel.topic:
        await interaction.response.send_message("You're already a fungus for this forest, silly.",ephemeral=True)
        return
    for i in interaction.channel.threads:
        if i.name.split("|",maxsplit=1)[-1] == str(interaction.author.id):
            await interaction.response.send_message(f"You already have a channel of your own: {i.mention}",ephemeral=True)
            return
    await interaction.response.send_message(f"{interaction.author.mention} has joined this forest.")

    thread: disnake.Thread = await interaction.channel.create_thread(name=f"{interaction.author.name}|{interaction.author.id}",
                                        auto_archive_duration=10080,type=disnake.ChannelType.private_thread)
    await thread.add_user(interaction.author)
    await thread.add_user(interaction.guild.me)
    await thread.add_user(await interaction.guild.get_or_fetch_member(int(interaction.channel.topic)))
    await thread.send(f"{interaction.author.mention}: this is your channel. Here your fungus will provide you with the information you need. For now, all you have to do is create yourself some basic backstory and just introduce yourself!")


@client.slash_command(name="addxp",description="Add XP (admin command)")
async def addxp(interaction: disnake.ApplicationCommandInteraction,
               xp: int,
               user: disnake.Member = commands.Param(
                    default=None, 
                    description="The user to give XP to"
                )):
    if not is_admin(interaction.author):
        await interaction.response.send_message("You can't do that.",ephemeral=True)
        return
    user = user or interaction.author
    add_user_xp(user.id,xp)
    await interaction.response.send_message(f"Added {xp} XP to {user.mention}. Now they have {get_user_xp(user.id)} XP.",ephemeral=True)


async def count_user_chars_in_thread(thread: disnake.Thread, user: disnake.Member, fungus: disnake.Member):
    total_chars_user = 0
    total_chars_fungus = 0
    async for message in thread.history(limit=None):
        if message.author == user:
            total_chars_user += len(message.content)
        elif message.author == fungus:
            total_chars_fungus += len(message.content)
    return total_chars_user,total_chars_fungus
async def close_thread_and_count_xp(channel: disnake.Thread, thread_owner_user: disnake.Member,fungus_user: disnake.Member):
    user_chars,fungus_chars = await count_user_chars_in_thread(channel,thread_owner_user,fungus_user)
    await channel.send(f"{thread_owner_user} has typed {user_chars} characters and will receive {user_chars//16} XP.\n{fungus_user} has typed {fungus_chars} characters and will receive {fungus_chars//8} XP. (Fungi get a 2x bonus)")
    add_user_xp(thread_owner_user.id,user_chars//16)
    add_user_xp(fungus_user.id,fungus_chars//8)


@client.slash_command(name="archive",description="Archive a tree chat or an entire forest.")
async def archive(interaction: disnake.ApplicationCommandInteraction):
    if interaction.channel.category.id != get_server_forest_category(interaction.guild.id):
        await interaction.response.send_message("This can only be used in forest chats or in tree threads.",ephemeral=True)
        return
    if isinstance(interaction.channel,disnake.Thread):
        thread_owner = await interaction.guild.get_or_fetch_member(int(interaction.channel.name.split("|",maxsplit=1)[-1]))
        fungus = await interaction.guild.get_or_fetch_member(int(interaction.channel.parent.topic))
        if interaction.author != thread_owner\
            and not is_admin(interaction.author)\
            and fungus!=interaction.author:
            await interaction.response.send_message("Only the fungus, the tree and admins may archive threads.",ephemeral=True)
            return
        await interaction.response.send_message("**This thread is now closed. The story is over for this tree, yet other trees continue on.**")
        await interaction.channel.edit(archived=True)
        await close_thread_and_count_xp(interaction.channel,thread_owner,fungus)
        return
    fungus = await interaction.guild.get_or_fetch_member(int(interaction.channel.topic))
    if interaction.author != fungus and not is_admin(interaction.author):
        await interaction.response.send_message("Only the fungus and admins may archive threads.",ephemeral=True)
        return
    await interaction.response.send_message("This forest is now but a thing of the past. All the stories are finished, and can be discussed.")
    await interaction.channel.edit(category=client.get_channel(get_server_archive_category(interaction.guild.id)))
    for i in interaction.channel.threads:
        thread_owner = await interaction.guild.get_or_fetch_member(int(i.name.split("|",maxsplit=1)[-1]))
        await close_thread_and_count_xp(i,thread_owner,await interaction.guild.get_or_fetch_member(interaction.channel.topic))
        await i.edit(archived=False,invitable=True)
        await i.send("*This thread is now public and open for discussion.*")
    async for i in interaction.channel.archived_threads():
        await i.edit(archived=False,invitable=True)
        await i.send("*This thread is now public and open for discussion.*")


@client.slash_command(name="forestbc",description="Forest broadcast: send a message to the entire forest.")
async def forestbc(interaction: disnake.ApplicationCommandInteraction,message: str):
    if interaction.channel.category.id != get_server_forest_category(interaction.guild.id):
        await interaction.response.send_message("This can only be used in main forest chats.",ephemeral=True)
        return
    channel = interaction.channel.parent if isinstance(interaction.channel,disnake.Thread) else interaction.channel
    for i in channel.threads:
        await i.send(message)


@client.slash_command(name="deleteforest",description="Delete the forest completely, without archiving or awarding XP")
async def deleteforest(interaction: disnake.ApplicationCommandInteraction):
    if not is_admin(interaction.author):
        await interaction.response.send_message("You can't do that.",ephemeral=True)
        return
    await interaction.channel.delete()


client.run(os.environ.get("DISCORD_TOKEN"))