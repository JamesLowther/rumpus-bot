#!/usr/bin/python3

import discord
from discord.ext import commands
import json
import os, sys, re, sqlite3

CONFIG_FILE = os.path.dirname(os.path.realpath(__file__)) + '/config.json'

# Set from json
BOT_TOKEN = None
ROOT_IDS = None
TREASON_WORDS = None
GOOD_WORDS = None

PREFIX = "$rumpus "

#db connection
DB_PATH = None
DB_CONN = None
DB_CUR = None

bot = commands.Bot(command_prefix=PREFIX)

def main():

    read_json()
    connect_db()

    bot.run(BOT_TOKEN)

@bot.event
async def on_ready():
    print("Logged in as {0.user}".format(bot))

# default event (chatting)
@bot.event
async def on_message(ctx):

    if ctx.author == bot.user:
        return

    if ctx.content.startswith(PREFIX):
        message_content = ctx.content[len(PREFIX):len(ctx.content)+1]
        if (bot.get_command(message_content)):
            await bot.process_commands(ctx)

    else:
        await check_message(ctx)

# shuts down the bot if the correct user is called
@bot.command(name="shutdown")
async def shutdown(ctx):
    print (str(ctx.author.id) + " (" + str(ctx.author) + ") called for shutdown")

    if (ctx.author.id in ROOT_IDS):

        DB_CONN.close()

        await ctx.channel.send("The rumpus room remains unguarded. Tread carefully.")
        print("Shutting down bot")
        await bot.logout()

    else:
        await ctx.channel.send("Sorry! You don't have permission to do that!")

# reloads the bot
@bot.command(name="reload")
async def reload_bot(ctx):

    global TREASON_WORDS, GOOD_WORDS, ROOT_IDS
    
    if (ctx.author.id in ROOT_IDS):
        with open(CONFIG_FILE) as f:
            
            data = json.load(f)

            ROOT_IDS = data['root_ids']
            TREASON_WORDS = data['treasonous_words']
            GOOD_WORDS = data['good_words']

            f.close()

        await ctx.channel.send("Rumpus reload successful!")

    else:
        await ctx.channel.send("Sorry! You don't have permission to do that!")

# print the current results
@bot.command(name="results")
async def results(ctx):
    DB_CUR.execute('SELECT * FROM subjects ORDER BY points DESC LIMIT 10;')
    results = DB_CUR.fetchall()

    if (not results):
        ctx.channel.send("Sorry, there are no results to display.")

    else:
        index_length = 3
        name_length = 17
        point_length = 10
        offense_length = 9
        deed_length = 5

        header = " "*index_length + "| NAME" + " "*(name_length - 4) + "| DOUBLOONS " + "| OFFENSES " + "| DEEDS"  "\n"

        to_send = "```\n"
        to_send += header
        to_send += "-"*len(header) + "\n"

        count = 1

        for row in results:

            to_send += str(count).ljust(index_length) + "| "

            if (len(row['name']) > name_length):
                to_send += row['name'][:name_length-1] + " "
            else:
                to_send += row['name'].ljust(name_length)

            to_send += "| " + str(row['points']).ljust(point_length)
            to_send += "| " + str(row['offenses']).ljust(offense_length)
            to_send += "| " + str(row['deeds']).ljust(deed_length) + "\n"

            count += 1
        
        DB_CUR.execute('SELECT * FROM subjects WHERE id=?;', (str(ctx.author.id),))
        row = DB_CUR.fetchone()

        if (row):
            DB_CUR.execute('SELECT * FROM subjects ORDER BY points DESC')
            results = DB_CUR.fetchall()

            i = results.index(row) + 1

            to_send += "-"*len(header) + "\n"
            
            to_send += str(i).ljust(index_length) + "| "

            if (len(row['name']) > name_length):
                to_send += row['name'][:name_length-1] + " "
            else:
                to_send += row['name'].ljust(name_length)

            to_send += "| " + str(row['points']).ljust(point_length)
            to_send += "| " + str(row['offenses']).ljust(offense_length)
            to_send += "| " + str(row['deeds']).ljust(deed_length) + "\n"


        to_send += "```"

        await ctx.channel.send(to_send)

# block the bot from sending messages
@bot.command(name="block")
async def block(ctx):
    DB_CUR.execute('SELECT * FROM subjects WHERE id=?', (str(ctx.author.id),))
    result = DB_CUR.fetchone()

    if (result):
        DB_CUR.execute('UPDATE subjects SET name=?, block=1 WHERE id=?', (str(ctx.author), str(ctx.author.id),))
    
    else:
        DB_CUR.execute('INSERT INTO subjects VALUES (?, ?, 1, 0, 0, 0);', (str(ctx.author.id), str(ctx.author)))

    DB_CONN.commit()

    await ctx.author.send("*Messages disabled*")

# unblock the bot from sending messaged
@bot.command(name="unblock")
async def unblock(ctx):
    DB_CUR.execute('SELECT * FROM subjects WHERE id=?', (str(ctx.author.id),))
    result = DB_CUR.fetchone()

    if (result):
        DB_CUR.execute('UPDATE subjects SET name=?, block=0 WHERE id=?', (str(ctx.author), str(ctx.author.id),))
    
    else:
        DB_CUR.execute('INSERT INTO subjects VALUES (?, ?, 0, 0, 0, 0);', (str(ctx.author.id), str(ctx.author)))

    DB_CONN.commit()

    await ctx.author.send("*Messages enabled*")

# connect to the database
def connect_db():

    global DB_CONN, DB_CUR

    DB_CONN = sqlite3.connect(DB_PATH)
    DB_CONN.row_factory = sqlite3.Row
    DB_CUR = DB_CONN.cursor()

    print("Connected to database at path: " + str(DB_PATH))

# read the configuration file
# sets the global variables
def read_json():

    with open(CONFIG_FILE) as f:
        data = json.load(f)

        global BOT_TOKEN, ROOT_IDS, TREASON_WORDS, GOOD_WORDS, DB_PATH

        BOT_TOKEN = data['bot_token']
        ROOT_IDS = data['root_ids']
        TREASON_WORDS = data['treasonous_words']
        GOOD_WORDS = data['good_words']
        DB_PATH = os.path.dirname(os.path.realpath(__file__)) + '/' + data['db_name']

        f.close()

        return

async def check_message(ctx):
    message_lower = ctx.content.lower()

    if (str(ctx.channel.type) == "private"):
        return

    if ("rumpus" in message_lower):

        # treason was spoken
        if re.compile('|'.join(TREASON_WORDS), re.IGNORECASE).search(message_lower):
            await handle_treason(ctx)

        # goodness was done
        if re.compile('|'.join(GOOD_WORDS), re.IGNORECASE).search(message_lower):
            await handle_good(ctx)

# handles treason
async def handle_treason(ctx):

    penalty = 30

    DB_CUR.execute('SELECT * FROM subjects WHERE id=?;', (str(ctx.author.id),))
    result = DB_CUR.fetchone()

    if (not result):
        DB_CUR.execute('INSERT INTO subjects VALUES (?, ?, 0, 1, 0, 0);', (str(ctx.author.id), str(ctx.author)))
        
        await ctx.author.send("HALT! I've caught wind that you've been speaking ill of the beloved rumpus room!\nYou will not be punished this time, but next time watch your tounge!\n*Note, if you would like to stop recieving these messages, type `$rumpus block`. Similarly, `$rumpus unblock` will allow these messages.\nYou can also type `$rumpus results` to see the current standings.*")

    else:
        points = result['points']
        offenses = result['offenses']

        DB_CUR.execute('UPDATE subjects SET name=?, points=?, offenses=? WHERE id=?', (str(ctx.author), points-penalty, offenses+1, str(ctx.author.id)))

        if (not result['block']):
            await ctx.author.send("What the heck! My sources say you are disrespecting the rumpus room! STOP IT! IT'S A REALLY COOL ROOM!\nI'm taking %d doubloons for your disrespect! You now have %d doubloons!" % (penalty, points-penalty))

    DB_CONN.commit()

# handles good messages
async def handle_good(ctx):

    benefit = 45

    DB_CUR.execute('SELECT * FROM subjects WHERE id=?;', (str(ctx.author.id),))
    result = DB_CUR.fetchone()

    if (not result):
        DB_CUR.execute('INSERT INTO subjects VALUES (?, ?, 0, 0, 1, ?);', (str(ctx.author.id), str(ctx.author), benefit))
        
        await ctx.author.send("Well done! My sources say you have been respecting the rumpus room! I'll give you %d doubloons for your good deed!\n*Note, if you would like to stop recieving these messages, type `$rumpus block`. Similarly, `$rumpus unblock` will allow these messages.\nYou can also type `$rumpus results` to see the current standings.*" % (benefit))

    else:
        points = result['points']
        deeds = result['deeds']

        DB_CUR.execute('UPDATE subjects SET name=?, points=?, deeds=? WHERE id=?', (str(ctx.author), points+benefit, deeds+1, str(ctx.author.id)))

        if (not result['block']):
            await ctx.author.send("Thank you for respecting the rumpus room! You really are a fantastic person!\nI'm giving you %d doubloons for your good behaviour! You now have %d doubloons!" % (benefit, points+benefit))

    DB_CONN.commit()

main()