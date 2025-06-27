import datetime
import os
import sys
import disnake
from disnake.ext import commands
import sqlite3
from dotenv import load_dotenv

load_dotenv()

intents = disnake.Intents.default()
intents.message_content = True

client = commands.InteractionBot(intents=disnake.Intents.default())

db: sqlite3.Connection = sqlite3.connect("db.sqlite3")
cur: sqlite3.Cursor = db.cursor()

creator_id: int = int(os.environ.get("CREATOR_USER_ID"))

tick_emoji = "✅"
thumbs_down = "👎"
thumbs_up = "👍"
ignore = "😐"
progress_bar_part1 = "⭐"
progress_bar_part2 = "▪️"

def create_user(id: int):
    cur.execute("INSERT INTO users ('userid') VALUES (?)",(id,))
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
    if not user_exists(id):
        create_user(id)
    cur.execute(f"UPDATE users SET {column} = {column} + ? WHERE userid = ?",(increment,id))
    db.commit()
def add_user_games(id: int, increment: int = 1): increase_user_value(id,increment,"played_games")
def add_user_controlled_games(id: int, increment: int = 1): increase_user_value(id,increment,"controlled_games")
def add_user_xp(id: int, increment: int = 1):
    data = cur.execute("SELECT strikes,xp_until_pardon FROM users WHERE userid = ?",(id,)).fetchone()
    if data is None: return
    strikes,xp_until_pardon = data
    if strikes>0:
        increase_user_value(id,increment,"xp_until_pardon")
        if xp_until_pardon+increment>=100:
            to_remove = min((xp_until_pardon+increment)//500,strikes)
            increase_user_value(id,-to_remove,"strikes")
            increase_user_value(id,-to_remove*500,"xp_until_pardon")
    increase_user_value(id,increment,"xp")
def add_user_strike(id: int, increment: int = 1): increase_user_value(id,increment,"strikes")

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
def get_user_controlled_games(id: int):
    return r[0] if (r:=cur.execute("SELECT controlled_games FROM users WHERE userid = ?",(id,)).fetchone()) is not None else None
def get_user_strikes(id: int):
    return r[0] if (r:=cur.execute("SELECT strikes FROM users WHERE userid = ?",(id,)).fetchone()) is not None else None
def get_user_xp_until_pardon(id: int):
    return r[0] if (r:=cur.execute("SELECT xp_until_pardon FROM users WHERE userid = ?",(id,)).fetchone()) is not None else None


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}. Creator ID: {creator_id}')

@client.event
async def on_raw_reaction_add(payload: disnake.RawReactionActionEvent):
    guild = await client.fetch_guild(payload.guild_id)
    channel = await guild.fetch_channel(payload.channel_id)
    user = await guild.get_or_fetch_member(payload.user_id)
    message = await channel.fetch_message(payload.message_id)

    if user.bot: return
    if isinstance(channel,disnake.Thread) and channel.locked:
        parent = await guild.fetch_channel(channel.parent_id)
        if parent.category_id != get_server_forest_category(payload.guild_id):
            return
        if not is_admin(user):
            await message.remove_reaction(payload.emoji, user)
            return
        if str(payload.emoji) == ignore: return
        userid = int(channel.name.split("|",maxsplit=1)[-1])
        if str(payload.emoji) == thumbs_up:
            add_user_xp(userid,-50)
            add_user_strike(userid)
            await channel.delete()
            return
        if str(payload.emoji) == thumbs_down:
            fungusid = int(channel.parent.topic)
            await channel.edit(locked=False)
            close_thread_and_count_xp(channel,await client.get_or_fetch_user(userid), await client.get_or_fetch_user(fungusid), 0.25, 0)
            add_user_xp(fungusid,-150)
            add_user_strike(fungusid)
            await channel.send("The fungus was issued a strike and given a penalty of 150 XP.")
        return
    if channel.category_id is None or channel.category_id != get_server_forest_category(payload.guild_id):
        return
    if str(payload.emoji) != thumbs_down: return
    msg = message.content
    if not msg.startswith(tick_emoji):
        return
    if not is_admin(user) and user.id!=int(channel.topic):
        await message.remove_reaction(payload.emoji, user)
        return
    (await guild.fetch_channel(int(msg.split(maxsplit=2)[1][2:-1]))).edit(locked=True)


@client.slash_command(name="hello",description="Test whether the bot is up")
async def hello_command(ctx: disnake.ApplicationCommandInteraction):
    await ctx.response.send_message(f"Hello world! (Your user id is {ctx.author.id})",ephemeral=True)


@client.slash_command(name="setthreshold",description="Set a threshold for the required XP level to be considered a fungus")
async def set_threshold(ctx: disnake.ApplicationCommandInteraction, xp: int = 500):
    if not is_admin(ctx.author):
        await ctx.response.send_message("You can't do that.",ephemeral=True)
        return
    set_server_fungus_threshold(ctx.guild.id,xp)
    await ctx.response.send_message(f"New threshold set! Now a player needs to have {xp} XP to be a fungus.",
                                            ephemeral=True)
    

@client.slash_command(name="createforest",description="Creates a new forest (only available to fungi)")
async def create_forest(ctx: disnake.ApplicationCommandInteraction, name: str):
    userxp = get_user_xp(ctx.user.id)
    needed = get_needed_server_xp(ctx.guild.id)
    if needed is None:
        await ctx.response.send_message("This server is not registered yet. An admin can register the server using /registerserver.",ephemeral=True)
        return
    if userxp is None:
        create_user(ctx.author.id)
        await ctx.response.send_message(f"You are not a fungus. You have 0 XP but {needed} is required.",ephemeral=True)
        return
    if userxp < needed:
        await ctx.response.send_message(f"You are not a fungus. You have {userxp} XP but {needed} XP is required.",ephemeral=True)
        return
    await ctx.response.send_message(f"Creating a new forest with the name of {name}...",ephemeral=True)
    channel = await ctx.guild.create_text_channel(
        name=f"{name}-by-{ctx.author.name}",
        category=client.get_channel(get_server_forest_category(ctx.guild.id)),
        topic=str(ctx.user.id)
    )
    await ctx.followup.send(
        f"Created a new forest: {channel.mention}. Use /join to become a tree in this forest.\nFungus: {ctx.author.mention}"
    )


@client.slash_command(name="registerserver",description="Register the server to allow creating forests")
async def register_server(ctx: disnake.ApplicationCommandInteraction,
                          forestcategory: disnake.CategoryChannel = commands.Param(name="forest_category",
                        description="The category which the bot will use to create channels"),
                        archivecategory: disnake.CategoryChannel = commands.Param(name="archive_category",
                        description="The category which be used for storing archived forests")
                        ):
    if server_exists(ctx.guild.id):
        remove_server(ctx.guild.id)
    if not is_admin(ctx.author):
        await ctx.response.send_message("You can't do that.",ephemeral=True)
        return
    add_server(ctx.guild.id,500,forestcategory.id,archivecategory.id)
    await ctx.response.send_message(f"Added this server to the database. Now the bot will use the {forestcategory.mention} category to create forests. Archived forests will be stored in {archivecategory.mention}.")


@client.slash_command(name="stats",description="See user stats")
async def stats(ctx: disnake.ApplicationCommandInteraction,
                user: disnake.Member = commands.Param(
                    default=None, 
                    description="The user to get info about (defaults to you)"
                )):
    user = user or ctx.author
    if not user_exists(user.id):
        await ctx.response.send_message("This user hasn't participated in any forests yet!",ephemeral=True)
        return
    await ctx.response.send_message(f"""{user.mention}:
XP: {get_user_xp(user.id)}/{get_needed_server_xp(ctx.guild.id)}
Games played as a tree: {get_user_games(user.id)}
Players controlled as a fungus: {get_user_controlled_games(user.id)}{f'\n\n**Strikes: {a}**' if (a:=get_user_strikes(user.id))>0 else ''}""",ephemeral=True)


@client.slash_command(name="join",description="Join a forest (create a private thread for you and the fungus)")
async def join(ctx: disnake.ApplicationCommandInteraction):
    category = get_server_forest_category(ctx.guild.id)
    if ctx.channel.category.id != category:
        await ctx.response.send_message(f"This is not a forest channel. Only channels in {client.get_channel(category).mention} are considered forests.",ephemeral=True)
        return
    if str(ctx.author.id) == ctx.channel.topic:
        await ctx.response.send_message("You're already a fungus for this forest, silly.",ephemeral=True)
        return
    for i in ctx.channel.threads:
        if i.name.split("|",maxsplit=1)[-1] == str(ctx.author.id):
            await ctx.response.send_message(f"You already have a channel of your own: {i.mention}",ephemeral=True)
            return
    thread: disnake.Thread = await ctx.channel.create_thread(name=f"{ctx.author.name}|{ctx.author.id}",
                                        auto_archive_duration=10080,type=disnake.ChannelType.private_thread)
    await ctx.response.send_message(f"{tick_emoji}: {thread.mention}\n<@{ctx.author.id}> has joined this forest.\n\n*The fungus can add the {thumbs_down} reaction to lock the thread immediately.*")
    strikes = get_user_strikes(ctx.author.id)
    if strikes is None: await ctx.followup.send(f"*Note: <@{ctx.author.id}> is a new player.* Welcome! We hope you stay. Have fun figuring things out!")
    elif strikes>0: await ctx.followup.send(f"**Note: <@{ctx.author.id}> has {strikes} strikes.** Keep an eye out on them, but don't be too harsh. <@{ctx.author.id}>, you need to receive {100-get_user_xp_until_pardon(ctx.author.id)} more XP to remove one strike.")
    await thread.add_user(ctx.author)
    await thread.add_user(ctx.guild.me)
    await thread.add_user(await ctx.guild.get_or_fetch_member(int(ctx.channel.topic)))
    await thread.send(f"{ctx.author.mention}: this is your channel. Here your fungus will provide you with the information you need. For now, all you have to do is create yourself some basic backstory and just introduce yourself!")


@client.slash_command(name="addxp",description="Add XP (admin command)")
async def addxp(ctx: disnake.ApplicationCommandInteraction,
               xp: int,
               user: disnake.Member = commands.Param(
                    default=None, 
                    description="The user to give XP to"
                )):
    if not is_admin(ctx.author):
        await ctx.response.send_message("You can't do that.",ephemeral=True)
        return
    user = user or ctx.author
    add_user_xp(user.id,xp)
    await ctx.response.send_message(f"Added {xp} XP to {user.mention}. Now they have {get_user_xp(user.id)} XP.",ephemeral=True)


async def count_user_chars_in_thread(thread: disnake.Thread, user: disnake.Member, fungus: disnake.Member, penalty_time: float = 7) -> tuple[int,int]:
    last_time_stamp: datetime.datetime = datetime.datetime(0)
    last_by_user = None
    total_chars_user = 0
    total_chars_fungus = 0
    async for message in thread.history(limit=None):
        if (message.created_at-last_time_stamp).total_seconds()<penalty_time and last_by_user==True and message.author != fungus: continue
        if message.author == user:
            total_chars_user += len(message.content)
            last_by_user = True
        elif message.author == fungus:
            total_chars_fungus += len(message.content)
            last_by_user = False
        last_time_stamp = message.created_at
    return total_chars_user,total_chars_fungus
async def close_thread_and_count_xp(channel: disnake.Thread,
                                    thread_owner_user: disnake.Member,
                                    fungus_user: disnake.Member,
                                    thread_owner_factor: float = 0.0625,
                                    fungus_factor: float = 0.125):
    user_chars,fungus_chars = await count_user_chars_in_thread(channel,thread_owner_user,fungus_user)
    await channel.send(f"{thread_owner_user} has typed {user_chars} characters and will receive {int(user_chars*thread_owner_factor)} XP (Bonus: {0.0625/thread_owner_factor if thread_owner_factor!=0 else 0}x).\n{fungus_user} has typed {fungus_chars} characters and will receive {int(fungus_chars*fungus_factor)} XP. (Bonus: {0.0625/fungus_factor if fungus_factor!=0 else 0}x)")
    add_user_games(thread_owner_user.id)
    add_user_controlled_games(fungus_user.id)
    add_user_xp(thread_owner_user.id,int(user_chars*thread_owner_factor))
    add_user_xp(fungus_user.id,int(fungus_chars*fungus_factor))


@client.slash_command(name="archive",description="Archive a tree chat or an entire forest.")
async def archive(ctx: disnake.ApplicationCommandInteraction):
    if ctx.channel.category.id != get_server_forest_category(ctx.guild.id):
        await ctx.response.send_message("This can only be used in forest chats or in tree threads.",ephemeral=True)
        return
    if isinstance(ctx.channel,disnake.Thread):
        thread_owner = await ctx.guild.get_or_fetch_member(int(ctx.channel.name.split("|",maxsplit=1)[-1]))
        fungus = await ctx.guild.get_or_fetch_member(int(ctx.channel.parent.topic))
        if ctx.author != thread_owner\
            and not is_admin(ctx.author)\
            and fungus!=ctx.author:
            await ctx.response.send_message("Only the fungus, the tree and admins may archive threads.",ephemeral=True)
            return
        await ctx.response.send_message("**This thread is now closed. The story is over for this tree, yet other trees continue on.**")
        await ctx.channel.edit(archived=True)
        await close_thread_and_count_xp(ctx.channel,thread_owner,fungus)
        return
    fungus = await ctx.guild.get_or_fetch_member(int(ctx.channel.topic))
    if ctx.author != fungus and not is_admin(ctx.author):
        await ctx.response.send_message("Only the fungus and admins may archive threads.",ephemeral=True)
        return
    await ctx.response.send_message("This forest is now but a thing of the past. All the stories are finished, and can be discussed.")
    await ctx.channel.edit(category=client.get_channel(get_server_archive_category(ctx.guild.id)))
    for i in ctx.channel.threads:
        thread_owner = await ctx.guild.get_or_fetch_member(int(i.name.split("|",maxsplit=1)[-1]))
        await close_thread_and_count_xp(i,thread_owner,await ctx.guild.get_or_fetch_member(ctx.channel.topic))
        await i.edit(archived=False,invitable=True)
        await i.send("*This thread is now public and open for discussion.*")
    async for i in ctx.channel.archived_threads():
        await i.edit(archived=False,invitable=True)
        await i.send("*This thread is now public and open for discussion.*")


@client.slash_command(name="forestbc",description="Forest broadcast: send a message to the entire forest.")
async def forestbc(ctx: disnake.ApplicationCommandInteraction,message: str):
    if ctx.channel.category.id != get_server_forest_category(ctx.guild.id):
        await ctx.response.send_message("This can only be used in main forest chats.",ephemeral=True)
        return
    channel = ctx.channel.parent if isinstance(ctx.channel,disnake.Thread) else ctx.channel
    if ctx.author.id != int(channel.topic):
        await ctx.response.send_message("This can only be done by fungi or admins.",ephemeral=True)
    await ctx.response.send_message("Sending...",ephemeral=True)
    for i in channel.threads:
        await i.send(message)


@client.slash_command(name="deleteforest",description="Delete the forest completely, without archiving or awarding XP")
async def deleteforest(ctx: disnake.ApplicationCommandInteraction):
    if not is_admin(ctx.author) or ctx.channel.category_id != get_server_forest_category(ctx.guild_id):
        await ctx.response.send_message("You can't do that.",ephemeral=True)
        return
    await ctx.channel.delete()


@client.slash_command(name="report",description="Report a tree or a fungus. This will lock the thread for further evaluation by the admins.")
async def report(ctx: disnake.ApplicationCommandInteraction):
    if not isinstance(ctx.channel,disnake.Thread):
        await ctx.response.send_message("This can only be done in tree channels.",ephemeral=True)
        return
    if not is_admin(ctx.author):
        await ctx.response.send_message("This can only be done by admins or fungi.",ephemeral=True)
        return
    await ctx.response.defer()
    msg = await ctx.followup.send(f"**Thread reported and locked. The player and the fungi will not receive XP for this.**\nAdmins: react {thumbs_up} to remove XP from the user and issue a strike.\nReact {ignore} to ignore.\nReact {thumbs_down} to unlock this thread, calculate user reward with bonus and issue a strike to the fungus.",wait=True)
    await msg.add_reaction(thumbs_down)
    await msg.add_reaction(ignore)
    await msg.add_reaction(thumbs_up)
    await ctx.channel.edit(locked=True,archived=True)


@client.slash_command(name="rate",description="Rate a player on a scale from 0-10 by flow and creativity. (/ratinghelp)")
async def rate(ctx: disnake.ApplicationCommandInteraction,
               flow: int = commands.Param(description="Rating between 0-10", gt=-1, lt=11),
               creativity: int = commands.Param(description="Rating between 0-10", gt=-1, lt=11)):
    if not isinstance(ctx.channel,disnake.Thread) or ctx.channel.category_id!=get_server_forest_category(ctx.guild_id):
        await ctx.response.send_message("This command can only be used in a tree thread.",ephemeral=True)
        return
    if ctx.author.id != int(ctx.channel.parent.topic):
        await ctx.response.send_message("Only the fungus can rate players.",ephemeral=True)
        return
    await ctx.response.send_message(f"""Rated by the fungus:
Flow: {progress_bar_part1*flow}{progress_bar_part2*(10-flow)} {flow}/10
Creativity: {progress_bar_part1*creativity}{progress_bar_part2*(10-creativity)} {creativity}/10
Total XP boost: {(flow+creativity)*5} XP""")
    add_user_xp(await ctx.guild.get_or_fetch_member(int(ctx.channel.name.split("|",maxsplit=1)[-1])), (flow+creativity)*5)



@client.slash_command(name="help",description="Show all commands")
async def help(ctx: disnake.ApplicationCommandInteraction):
    await ctx.send(f"""/hello - ping the bot
/stats - shows stats of you or another user
/join - when used in a forest channel, joins the forest, creating your personal thread.
/createforest - create your own forest. ({get_needed_server_xp(ctx.guild_id)} XP required)
/report - when used in a tree thread, reports either the user or the fungus. Locks the thread. Admins will review the content.
/archive - when used in a tree thread, archives it and rewards XP to the user and the fungus.

**Fungi:**
/forestbc - forest broadcast, send a message into every tree thread in the forest.
/archive - archives all the tree threads in a forest, rewarding XP.
/rate - rate your players by flow and creativity! This will award them with extra XP.

**Admins:**
/addxp - adds XP
/deleteforest - deletes a forest completely, without awarding XP.
/setthreshold - set the XP threshold for the ability to create a forest.""",ephemeral=True)
    

@client.slash_command(name="ratinghelp",description="Rating guide for fungi")
async def ratinghelp(ctx: disnake.ApplicationCommandInteraction):
    await ctx.response.send_message("""**Rating Guide for Fungi**
Rating criteria:
- *Flow* (ability to move with the current and compromise if things don't go the player's way)
- *Creativity* (imagination and adaptability that the roleplayer brings to the table)""",ephemeral=True)


client.run(os.environ.get("DISCORD_TOKEN"))