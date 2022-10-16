# SDVAutumn2022
# main.py
# Written by blueberry et al., 2022
# https://github.com/StardewValleyDiscord/SDVAutumn2022

import asyncio
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

from discord import AllowedMentions, Guild
from discord.ext import commands
from discord.ext.commands import Context
from importlib import reload

import config
import db
import err
import strings
import utils
from config import COMMAND_PREFIX, EXTENSIONS, DISCORD_INTENTS, ROLE_ADMIN, ROLE_HELPER
from utils import check_roles

"""
Contents:
    Logging
    Bot definition
        SBot
    Init
    Global commands
    Discord.py boilerplate
"""


# Logging


logger: logging.Logger = logging.getLogger("discord")
handler: RotatingFileHandler = RotatingFileHandler(
    filename=config.PATH_LOG,
    encoding="utf-8",
    maxBytes=config.LOG_SIZE_MEBIBYTES * 1024 * 1024,
    backupCount=config.LOG_BACKUP_COUNT
)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)


# Bot definition


class SBot(commands.Bot):
    """
    Bot used for Stardew Valley Discord 2022 Sideshow event.
    Includes methods for updating and reloading commands and strings during runtime.
    """
    def __init__(self):
        super().__init__(
            command_prefix=COMMAND_PREFIX,
            intents=DISCORD_INTENTS,
            description=strings.get("client_description"),
            allowed_mentions=AllowedMentions.none())

        self.db = db
        """Bot database instance."""

    async def setup_hook(self):
        """
        Inherited from Client. Called once internally after login. Used to load all initial command extensions.
        """
        # Load database
        db.setup()
        # Load all extensions on setup
        for ext in EXTENSIONS:
            await self.load_extension(name=ext)

    async def on_ready(self):
        """
        Inherited from Client. Called once internally after all setup. Used only to log notice.
        """
        msg = strings.get("client_login").format(
            self.user.name,
            self.user.discriminator,
            self.user.id)
        print(msg)

    async def sync_guild(self, guild: Guild):
        """
        Syncs app commands from this bot with the remote Discord state when required to apply changes.
        :param guild: Discord guild to sync commands with.
        """
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    def reload_strings(self) -> None:
        """
        Reloads all text strings from data file for bot commands and interactions.
        """
        reload(strings)
        reload(utils)

    async def on_command_error(self, ctx: Context, error: Exception) -> None:
        """
        Additional behaviours on errors using commands to either suppress, react, or reply.
        """
        # Add a reaction to posts with unknown commands or invalid uses
        msg: Optional[str] = None
        reaction: Optional[str] = None
        try:
            if isinstance(error, commands.CheckFailure):
                # Suppress failed command checks
                reaction = strings.emoji_error
            elif isinstance(error, commands.errors.CommandNotFound):
                # Suppress failed command calls
                reaction = strings.emoji_question
            elif isinstance(error, commands.errors.BadArgument):
                # Suppress failed command parameters
                reaction = strings.emoji_exclamation
            else:
                if isinstance(error, TimeoutError):
                    # Send message on connection timeout
                    msg = strings.get("info_connection_timed_out").format(strings.emoji_connection)
                reaction = strings.emoji_error
                err.log(error)
                raise error
        finally:
            if msg:
                await ctx.reply(content=msg)
            if reaction:
                await ctx.message.add_reaction(reaction)


# Init


bot = SBot()
"""Main instance of the bot."""

# Global commands

@bot.command(name="ping")
async def cmd_ping(ctx: Context):
    await ctx.reply(content="pong")

@bot.check
async def is_valid_command_use(ctx: Context) -> bool:
    """
    Global check to determine whether a given command should be processed.
    """
    # Ignore commands from bots
    is_not_bot: bool = not ctx.author.bot

    # Ignore commands from channels other than the designated text channel (except admin commands used by admins)
    is_channel_ok: bool = ctx.channel.id in config.CHANNEL_COMMANDS or check_roles(ctx.author, [ROLE_ADMIN, ROLE_HELPER])

    return is_not_bot and is_channel_ok


# Discord.py boilerplate

# Run bot
async def main():
    async with bot:
        await bot.start(token=config.TOKEN_DISCORD)

asyncio.run(main=main())
