import logging
import os
import sys
import traceback
from functools import wraps, reduce
from importlib import import_module

import discord

import GoogleAPI
import RiotAPI
from linkbot.errors import *
from linkbot.utils.ini import IniIO
from linkbot.utils import emoji
import linkbot.utils.database as db
from linkbot.utils.command import Command
from linkbot.utils.misc import load_json, create_config, split_message

DATA_FOLDER = 'data/'
CONFIG_FILE = 'config.ini'
SUGGESTION_FILE = DATA_FOLDER + 'suggestions.txt'
DATABASE_FILE = DATA_FOLDER + 'database.json'
REMINDERS_FILE = DATA_FOLDER + 'reminders.json'
client = discord.Client()


class LinkBot:
    def __init__(self):
        # If the config file doesn't exist, create it with the defaults.
        if not os.path.isfile(CONFIG_FILE):
            create_config(CONFIG_FILE)
            raise InitializationError("Config has been created. Fill out the required information before continuing.")

        self.restart = False
        self.paused = False

        self.lolgame_region = 'na'
        self.commands = {}
        self.events = {}
        self.data = load_json(DATABASE_FILE)
        # { serverID: {
        #       "admins" : [ userID, ... ],
        #       "birthdays" : { name : birthday, ...},
        #       "quotes" : [ ( text, author ), ... ]
        # }

        # All server ids are stored as strings by the json module.
        # Thus, they must get converted into integers here before they can be used with discord.py.
        records = [(key, val) for (key, val) in self.data.items()]
        for (key, val) in records:
            self.data[int(key)] = val
            del self.data[key]

        options = IniIO.load(CONFIG_FILE)
        self.owner_id = options.get_int('ownerDiscordId', default=None)
        self.owner = None
        self.token = options.get_str('bot.token', default=None)
        self.client_id = options.get_int('bot.clientId', default=None)
        self.client_secret = options.get_str('bot.clientSecret', default=None)
        self.prefix = options.get_str('prefix', default=None)
        google_apikey = options.get_str('apikeys.google', default=None)
        self.googleClient = GoogleAPI.Client(google_apikey) if google_apikey is not None else None
        riot_apikey = options.get_str('apikeys.riotgames', default=None)
        self.riotClient = RiotAPI.Client(riot_apikey) if riot_apikey is not None else None
        self.debug = options.get_bool('debug')

        if self.token is None or self.client_id is None or self.client_secret is None:
            raise InitializationError("'token', 'clientId', and 'clientSecret' must be specified in {}."
                                      .format(CONFIG_FILE))
        if self.owner_id is None:
            raise InitializationError("'ownerDiscordId' must be specified with your Discord user ID in {}."
                                      .format(CONFIG_FILE))
        if self.prefix is None:
            raise InitializationError("'prefix' must be specified in {} for proper functionality."
                                      .format(CONFIG_FILE))


    def run(self):
        logging.info('Initializing and logging in...')
        client.run(self.token)
        logging.info('Bot has been logged out.')
        if self.restart:
            logging.info("Restarting...")
            os.execl(sys.executable, sys.executable, *sys.argv)


bot = LinkBot()


def event(func):
    e = func.__name__[3:]
    @client.event
    @wraps(func)
    async def wrapper(*args, **kwargs):
        await func(*args, **kwargs)
        if e in bot.events.keys():
            for f in bot.events[e]:
                await f(*args, **kwargs)
    bot.events[e] = []
    return wrapper


@event
async def on_ready():

    # load voice module
    # discord.opus.load_opus('opus')
    # if not discord.opus.is_loaded():
    #    await logging.info('WARNING:\tOpus failed to load. Voice is disabled for this session.')

    # :::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::
    # Print out various information about the bot for this session.
    # :::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

    bot.owner = client.get_user(bot.owner_id)
    if bot.owner is None:
        raise InitializationError("Bot owner could not be found in any servers that the bot is a part of.")
    logging.info('Prefix: ' + "'" + bot.prefix + "'")
    if bot.debug:
        await client.change_presence(activity=discord.Game('DEVELOPMENT'))
        logging.info('Currently running in DEBUG mode. Edit source with DEBUG = False to deactivate.')
    else:
        await client.change_presence(activity=discord.Game('{}help'.format(bot.prefix)))
    logging.info('LinkBot is ready.')


@event
async def on_member_join(member):
    pass


@event
async def on_guild_join(guild):
    # Add an entry for this guild into the database.
    with db.connect() as (conn, cur):
        cur.execute(
            """
            INSERT INTO servers (server_id)
            VALUES (%s);
            """, [guild.id])
        conn.commit()


@event
async def on_guild_remove(guild):
    with db.connect() as (conn, cur):
        cur.execute(
            """
            DELETE FROM servers
            WHERE server_id = %s
            CASCADE;
            """, [guild.id])
        conn.commit()


@event
async def on_message(message):
    if message.author.id != client.user.id:
        logging.info("Received a message from " + message.author.name)
        cmd = Command(bot, message)

        # if the message has the prefix or the channel is a DM, then the message is targeted at the bot.
        if cmd.has_prefix or cmd.is_dm:
            if not bot.paused or (bot.paused and cmd.command_arg.lower() == 'unpause'):
                if cmd.is_valid:
                    await cmd.run()
                else:
                    raise CommandError(cmd, '"{}" is not a valid command.'.format(cmd.command_arg))


@client.event
async def on_error(event_name, *args, **kwargs):
    etype, e, tb = sys.exc_info()
    fmt_exc = reduce(lambda x, y: "{}{}".format(x, y), traceback.format_exception(etype, e, tb), "")
    if etype is InitializationError:
        raise e
    if issubclass(etype, CommandError):
        ch = e.cmd.channel
        if etype is CommandSyntaxError:
            # TODO: subcmd = e.cmd.message.content[:e.cmd.message.content.find(e.cmd.argstr)].strip()
            await ch.send("{} {} Try `{}help {}` for help on how to use `{}`."
                          .format(emoji.warning, e, bot.prefix, e.cmd.command_arg, e.cmd.command_arg))
        elif etype is CommandPermissionError:
            await ch.send("{} {}".format(emoji.no_entry, e))
        elif etype is DeveloperError:
            await ch.send("{} {}".format(emoji.exclamation, e.public_reason))
            await _send_traceback(fmt_exc)
        elif etype is CommandError:
            await ch.send("{} {}".format(emoji.x, e))
    else:
        await _send_traceback(fmt_exc)


async def _send_traceback(tb):
    logging.error(tb)
    for msg in split_message(tb, 1994):
        await bot.owner.send("```{}```".format(msg))



# Database setup and test.
if not db.setup(CONFIG_FILE):
    raise InitializationError(
        "Failed to connect to the database. Be sure that your database settings in {} have been set up properly."
            .format(CONFIG_FILE))
try:
    with db.connect():
        pass
except:
    raise InitializationError("Failed to connect to the database. Is the hostname correct, and is the database online?")

# Import all commands.
cmd_dir = 'linkbot/commands/'
for file in [cmd_dir + f for f in os.listdir(cmd_dir)]:
    if os.path.isfile(file) and not file.endswith('__init__.py'):
        package = file.replace('/', '.')[:-3]
        _ = import_module(package)