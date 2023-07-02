# SDVAutumn2022
# utils.py
# Written by blueberry et al., 2022
# https://github.com/StardewValleyDiscord/SDVAutumn2022

import re
import typing

import discord
from discord import Member, User, PartialEmoji, Message, TextChannel, Guild, Forbidden, NotFound, Embed, Emoji
from discord.abc import GuildChannel
from discord.ext.commands import Context, Command, Bot
from config import CHANNEL_ROLES, ROLE_ADMIN
from typing import Any, List, Optional, Union

import strings


class CheckFailureQuietly(discord.ext.commands.CheckFailure):
    """
    Override for check failure error for specific error handling.
    """
    pass


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

def get_help_message(guild: Guild, bot: Bot, commands: Any) -> Embed:
    emoji: Emoji = discord.utils.get(bot.emojis, name=strings.get(strings.random("emoji_list")))
    embed_title = f"{emoji}\t{strings.get('help_title')}"
    embed_description: str = "\n".join(
        sorted([strings.get("help_command_format"
                            if not any(check.__name__ == requires_admin.__name__ for check in command.checks)
                            else "help_command_admin_format").format(
            command_signature_to_string(command=command),
            command.help.split("\n")[0] if command.help else ""
        ) for command in commands]))
    embed: Embed = Embed(
        title=embed_title,
        description=strings.get("help_content").format(embed_description),
        colour=guild.get_member(bot.user.id).colour)
    thumbnail_url: str = discord.utils.get(bot.emojis, name=strings.get("emoji_shop")).url
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    return embed

def command_signature_to_string(command: Command) -> str:
    string: str = command.name if not any(command.params) \
        else strings.get("commands_response_params_format").format(
            command.name,
            " ".join([("<{0}: {1}>" if param.required else "[{0}: {1}]").format(
                param.name,
                " | ".join([s for i, s in enumerate(str(param.annotation).split("\'")) if i % 2])
                if "\'" in str(param.annotation)
                else str(param.annotation))
                for param in command.params.values()]))
    return string

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
