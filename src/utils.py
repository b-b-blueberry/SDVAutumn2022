# SDVAutumn2022
# utils.py
# Written by blueberry et al., 2022
# https://github.com/StardewValleyDiscord/SDVAutumn2022

import re
import typing

from discord import Member, User, PartialEmoji, Message, TextChannel, Guild, Forbidden, NotFound
from discord.abc import GuildChannel
from discord.ext.commands import Context
from config import CHANNEL_ROLES, ROLE_ADMIN
from typing import Union, List, Optional


def format_roles_error(error: str, roles: List[str]) -> str:
    """
    :param error: Unformatted error message.
    :param roles: List of required roles to display in the error message.
    :return: Formatted error message.
    """
    return error.format(", ".join([f"<@&{role}>" for role in roles]), f"<#{CHANNEL_ROLES}>")

def check_roles(user: Union[User, Member], role_ids: List[int]) -> bool:
    """
    Check roles
    :param user: A user or member object, where a user that is not a member is ensured not to have any roles.
    :param role_ids: A list of role IDs to check for.
    :return: Whether a user has any of the roles in a given list.
    """
    return (isinstance(user, Member)
            and len(role_ids) > 0 and len([r for r in user.roles if r.id in role_ids]) > 0)

def requires_admin(ctx: Context) -> bool:
    """
    Command check for whether the author has an admin role.
    """
    return check_roles(ctx.message.author, [ROLE_ADMIN])

def get_message_emojis(mesage: Message) -> typing.List[PartialEmoji]:
    """
    Source: discord.py server.

    Returns a list of custom emojis in a message.
    """
    emojis = re.findall('<(?P<animated>a?):(?P<name>[\w]{2,32}):(?P<id>[\d]{18,22})>', mesage.content)
    return [PartialEmoji(animated=bool(animated), name=name, id=id) for animated, name, id in emojis]

def mention_to_id(mention: [str, int]) -> int:
    """
    Strips mention formatting from a Discord ID.
    :param mention: Discord ID or mention string.
    :return: Discord ID as digits only.
    """
    return int(re.sub("\D", "", mention))

def query_channel(guild: Guild, query: str) -> Optional[GuildChannel]:
    """
    Converts a Discord channel ID or mention to a channel instance, if a visible matching channel exists.
    :param guild:
    :param query: Discord channel ID or mention.
    :return: Channel instance, if found.
    """
    return guild.get_channel(mention_to_id(query))

async def get_guild_message(guild: Guild, message_id: int) -> Message:
    """
    Source: Governor by StardewValleyDiscord.

    Returns a message in a guild by querying individual channels.
    :param guild: Guild with channels to search in.
    :param message_id: Discord message ID to search for.
    :return: Message instance if found.
    """
    for channel in guild.channels:
        try:
            if isinstance(channel, TextChannel):
                message = await channel.fetch_message(int(message_id))
                return message
        except Forbidden as e:
            # Ignore channels we're unable to search
            if e.code == 50001:
                pass
        except NotFound as e:
            # Ignore channels that don't contain a matching message
            if e.code == 10008:
                pass
