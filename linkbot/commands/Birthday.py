
from linkbot.utils.cmd_utils import *
from linkbot.utils.misc import english_listing, parse_date
from linkbot.utils.search import get_guild_info_channel, search_members, resolve_search_results
from datetime import date, datetime


@command(
    ["{c} list", "{c} set <name> <mm/dd>", "{c} remove <name>"],
    "Set, remove, or list the registered birthdays from the database.",
    [
        ("{c} set Bill 04/20", "This will set Bill's birthday as April 20th."),
        ("{c} list", "will list all birthdays that are registered for this server."),
        ("{c} remove Bill", "will remove Bill's birthday from the system.")
    ],
    aliases=['bday']
)
@restrict(SERVER_ONLY)
@require_args(1)
async def birthday(cmd: Command):
    subcmd = cmd.args[0].lower()
    cmd.shiftargs()
    if subcmd == "set":
        await birthday_set(cmd)
    elif subcmd == "remove":
        await birthday_remove(cmd)
    elif subcmd == "list":
        await birthday_list(cmd)
    else:
        raise CommandSyntaxError(cmd, "Invalid subcommand.")


async def birthday_list(cmd):
    now = datetime.now()
    with db.Session() as sess:
        results = sess.get_guild_birthdays(cmd.guild.id)
    bdays = []
    for (p, b) in results:
        if b.month > now.month or (b.month == now.month and b.day >= now.day):
            bdays.append([cmd.guild.get_member(p), datetime(now.year, b.month, b.day)])
        else:
            bdays.append([cmd.guild.get_member(p), datetime(now.year + 1, b.month, b.day)])
    if len(bdays) == 0:
        raise CommandError(cmd, "I don't know anyone's birthdays yet.")
    bdays.sort(key=lambda x: x[1])

    send_msg = ""
    for (p, b) in bdays:
        send_msg += f"{p.display_name}: {b.strftime('%B %d')}\n"
    await cmd.channel.send(send_msg)


@restrict(ADMIN_ONLY)
@require_args(2)
async def birthday_set(cmd):
    person_search = cmd.args[0]
    bdayarg = cmd.args[1]
    # if specified that today is the birthday, set it.
    if bdayarg == "today":
        bday = date.today()
    # otherwise, we'll have to parse it out manually.
    else:
        try:
            bday = parse_date(bdayarg, cmd.args[2] if len(cmd.args) > 2 else "")
        except ValueError:
            # Send error: Invalid format.
            raise CommandSyntaxError(
                cmd, 'Birthdays must be in the format of TB 09/02, TB 09-02, TB Sep 02 or TB September 02.')

    # set the birthday for the server and person.
    async def local_birthday_set(member):
        with db.Session() as sess:
            sess.set_birthday(cmd.guild.id, member.id, bday)
        await send_success(cmd.message)

    bday = date(1, bday.month, bday.day)
    s_results = search_members(person_search, cmd.guild)
    await resolve_search_results(s_results, person_search, 'members', cmd.author, cmd.channel, local_birthday_set)



@restrict(ADMIN_ONLY)
@require_args(1)
async def birthday_remove(cmd):
    async def local_birthday_remove(member):
        with db.Session() as sess:
            sess.remove_birthday(cmd.guild.id, member.id)
        await send_success(cmd.message)

    person_search = cmd.args[0]
    s_results = search_members(person_search, cmd.guild)
    await resolve_search_results(s_results, person_search, 'members', cmd.author, cmd.channel, local_birthday_remove)


@background_task
async def birthday_check():
    while True:
        for guild in client.guilds:
            with db.Session() as sess:
                m_ids = sess.get_unrecognized_birthdays(guild.id)
                if m_ids:
                    names = [guild.get_member(m_id).display_name for m_id in m_ids]
                    people = english_listing(names)
                    channel = get_guild_info_channel(guild)
                    await channel.send(f"Happy birthday, {people}!")
                    sess.set_birthday_recognition(guild.id, m_ids)
        await asyncio.sleep(900)

