
from linkbot.utils import database as db
from linkbot.bot import bot
import discord
from typing import Union


def is_admin(member: discord.Member):
    """ Checks if the member is able to use admin commands. This can be an Admin, Bot owner, or Server owner. """
    if is_bot_owner(member) or is_server_owner(member):
        return True
    with db.Session() as sess:
        if sess.get_member_is_admin(member.guild.id, member.id):
            return True
    return False


def is_bot_owner(user: Union[discord.Member, discord.User]):
    """ Checks if the user is the owner of the bot. """
    return user == bot.owner


def is_server_owner(member: discord.Member):
    """ Checks if the member owns the server. """
    return member.guild.owner == member
