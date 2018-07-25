from Commands.CmdHelper import *

# add/remove/list admins for the server in which the cmd was received
def cmd_admin(cmd: Command):
    logging.info('Command: admin')

    # Check for args
    if len(cmd.args) == 0:
        cmd.on_syntax_error('')
        return

    # Check for using cmd on server.
    if cmd.guild is None:
        bot.send_message(cmd.channel, 'You can only use this command in a server.')
        return

    if cmd.guild.id not in bot.data:
        bot.data[cmd.guild.id] = {}
    if 'admins' not in bot.data[cmd.guild.id]:
        bot.data[cmd.guild.id]['admins'] = []

    # if "admin list"
    if cmd.args[0].lower() == "list":

        # Check for existing admins
        if len(bot.data[cmd.guild.id]['admins']) == 0:
            bot.send_message(cmd.channel, 'There are no admins on this server.')
            return

        # get the admin names from their IDs, save them to a string, then send it to the channel.
        admins = 'Admins: '
        needs_comma = False
        for member in cmd.guild.members:
            if member.id in bot.data[cmd.guild.id]['admins']:
                if needs_comma:
                    admins += ', '
                admins += member.name
                needs_comma = True
        bot.send_message(cmd.channel, admins)
        logging.info("Listed admins.")

    # if "admin add"
    elif cmd.args[0].lower() == "add":

        # Check that the sender is an admin
        if not bot.is_admin(cmd.author):
            bot.send_message(cmd.channel, "You must be an admin to use this command.")
            return

        # the output cmd at the end.
        msg = ''

        # if there is a member mention, add them as an admin.
        for member in cmd.message.mentions:
            if member.id in bot.data[cmd.guild.id]['admins']:
                msg += member.display_name + " is already an admin.\n"
            else:
                bot.data[cmd.guild.id]['admins'].append(member.id)
                msg += "Added " + member.display_name + " as an admin.\n"

        # if there is a role mention, add all members with that role as an admin.
        for role in cmd.message.role_mentions:
            for member in cmd.guild.members:
                if role in member.roles:
                    if member.id in bot.data[cmd.guild.id]['admins']:
                        msg += member.display_name + " is already an admin.\n"
                    else:
                        bot.data[cmd.guild.id]['admins'].append(member.id)
                        msg += "Added " + member.display_name + " as an admin.\n"
        # output
        bot.save_data()
        bot.send_message(cmd.channel, msg)
        logging.info("Added admins.")

    # if "admin remove"
    elif cmd.args[0].lower() == "remove":

        # Check that the sender is an admin.
        if not bot.is_admin(cmd.author):
            bot.send_message(cmd.channel, "You must be an admin to use this command.")
            return

        # the output message at the end.
        msg = ''

        # if there is a member mention, add them as an admin.
        for member in cmd.message.mentions:
            if member.id not in bot.data[cmd.guild.id]['admins']:
                msg += member.display_name + " is not an admin.\n"
            else:
                bot.data[cmd.guild.id]['admins'].remove(member.id)
                msg += "Removed " + member.display_name + " from the admin list.\n"

        # if there is a role mention, add all members with that role as an admin.
        for role in cmd.message.role_mentions:
            for member in cmd.guild.members:
                if role in member.roles:
                    if member.id not in bot.data[cmd.guild.id]['admins']:
                        msg += member.display_name + " is not an admin.\n"
                    else:
                        bot.data[cmd.guild.id]['admins'].remove(member.id)
                        msg += "Removed " + member.display_name + " from the admin list.\n"
        # output
        bot.save_data()
        bot.send_message(cmd.channel, msg)
        logging.info("Removed admins.")

    # if "admin ..."
    else:
        bot.send_message(cmd.channel, '{0} is not a valid argument.'.format(cmd.args[0]))
