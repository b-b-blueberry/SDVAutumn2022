# SDVAutumn2022
# config.py
# Written by blueberry et al., 2022
# https://github.com/StardewValleyDiscord/SDVAutumn2022

import os
from typing import List

import discord
import json

"""
Contents:
    Runtime
    Bot
    Tokens
    Discord
    Balance
    Fishing challenge
    Fortune teller
    Strength test
"""

# Runtime

LOG_DIR: str = "./private/logs"
"""Relative path to temporary folder used to store session logs."""
PATH_CONFIG: str = "./private/config.json"
"""Relative path to data file used for bot configuration."""
PATH_DATABASE: str = "./private/2023-summer.db"
"""Relative path to database file used to store usage history."""
PATH_STRINGS: str = "./assets/strings.json"
PATH_LOG: str = os.path.join(LOG_DIR, "discord.log")

# Parse config file
with open(file=PATH_CONFIG, mode="r", encoding="utf8") as config_file:
    cfg = json.load(config_file)

# Bot

COG_COMMANDS: str = "Sideshow Commands"
"""Name of commands cog."""
PACKAGE_COMMANDS: str = "commands"
"""Name of commands package."""
LOG_SIZE_MEBIBYTES: float = cfg["logging"]["file_size_mebibytes"]
LOG_BACKUP_COUNT: int = cfg["logging"]["backup_count"]

# Tokens

TOKEN_DISCORD: str = cfg["discord"]
"""Token used to run Discord client."""

# Discord

DISCORD_INTENTS: discord.Intents = discord.Intents(
    guilds=True,
    guild_messages=True,
    guild_reactions=True,
    message_content=True,
    emojis=True
)
"""List of allowed and disallowed intents when running Discord client."""
EXTENSIONS: List[str] = cfg["extensions"]
"""List of extensions to load on bot init."""
COMMAND_PREFIX: str = cfg["command_prefix"]
"""Prefix required for all messages sent in command channel."""

ROLE_EVENT: int = cfg["roles"]["event"]
ROLE_PICROSS: int = cfg["roles"]["picross"]
ROLE_HELPER: int = cfg["roles"]["helper"]
ROLE_ADMIN: int = cfg["roles"]["admin"]
"""Discord role ID for commands and features requiring admin privileges."""

CHANNEL_COMMANDS: List[int] = cfg["channels"]["commands"]
CHANNEL_SHOP: int = cfg["channels"]["shop"]
CHANNEL_ROLES: List[int] = cfg["channels"]["roles"]

CHANNEL_SUBMIT_ART: int = cfg["channels"]["submit_art"]
CHANNEL_SUBMIT_MODS: int = cfg["channels"]["submit_mods"]
CHANNEL_SUBMIT_WRITING: int = cfg["channels"]["submit_writing"]
CHANNEL_SUBMIT_DECOR: int = cfg["channels"]["submit_decor"]
CHANNEL_SUBMIT_HATS: int = cfg["channels"]["submit_hats"]
CHANNEL_SUBMIT_PICROSS: int = cfg["channels"]["submit_picross"]
CHANNEL_VERIFY_PICROSS: int = cfg["channels"]["verify_picross"]

# Balance

STARTING_BALANCE: int = cfg["balance"]["starting_balance"]

# Submissions

SUBMISSION_ENABLED: bool = cfg["submissions"]["enabled"]
SUBMISSION_VALUE_ART: int = cfg["submissions"]["value_art"]
SUBMISSION_VALUE_MODS: int = cfg["submissions"]["value_mods"]
SUBMISSION_VALUE_WRITING: int = cfg["submissions"]["value_writing"]
SUBMISSION_VALUE_DECOR: int = cfg["submissions"]["value_decor"]
SUBMISSION_VALUE_HATS: int = cfg["submissions"]["value_hats"]

# Picross

PICROSS_AWARDS: List[dict] = sorted(cfg["picross"]["awards"], key=lambda entry: entry.get("value"))

# Shop

SHOP_ROLE_LIST: List[dict] = sorted(cfg["shop"]["role_list"], key=lambda entry: entry.get("cost"))

