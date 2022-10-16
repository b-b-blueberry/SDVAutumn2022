# SDVAutumn2022
# config.py
# Written by blueberry et al., 2022
# https://github.com/StardewValleyDiscord/SDVAutumn2022

from typing import List, Dict

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

PATH_CONFIG: str = "./private/config-bb.json"
"""Relative path to data file used for bot configuration."""
PATH_DATABASE: str = "./private/autumn-bb.db"
"""Relative path to database file used to store usage history."""
PATH_STRINGS: str = "./assets/strings.json"
PATH_LOG: str = "./private/discord.log"

# Parse config file
with open(PATH_CONFIG) as config_file:
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
ROLE_HELPER: int = cfg["roles"]["helper"]
ROLE_ADMIN: int = cfg["roles"]["admin"]
"""Discord role ID for commands and features requiring admin privileges."""

CHANNEL_COMMANDS: List[int] = cfg["channels"]["commands"]
CHANNEL_SHOP: int = cfg["channels"]["shop"]
CHANNEL_ART: int = cfg["channels"]["art"]
CHANNEL_FOOD: int = cfg["channels"]["food"]
CHANNEL_FISHING: int = cfg["channels"]["fishing"]
CHANNEL_ROLES: List[int] = cfg["channels"]["roles"]

# Balance

STARTING_BALANCE: int = cfg["balance"]["starting_balance"]

# Submissions

SUBMISSION_ENABLED: bool = cfg["submissions"]["enabled"]
SUBMISSION_ART_VALUE: int = cfg["submissions"]["art_value"]
SUBMISSION_FOOD_VALUE: int = cfg["submissions"]["food_value"]

# Fishing challenge

FISHING_ENABLED: bool = cfg["fishing"]["enabled"]
FISHING_BONUS_CHANCE: float = cfg["fishing"]["bonus_chance"]
FISHING_BONUS_VALUE: int = cfg["fishing"]["bonus_value"]
FISHING_HIGH_VALUE: int = cfg["fishing"]["high_value"]
FISHING_DURATION_SECONDS: int = cfg["fishing"]["duration_seconds"]
FISHING_SCOREBOARD: Dict[str, int] = {
    "SDVitemtuna": 5,
    "SDVitembass": 5,
    "SDVpufferfish": 10,
    "SDVitemblobfish": 15,
    "SDVitemtreasure": 15,
    "\N{NEWSPAPER}": 1,
    "\N{EYEGLASSES}": 1,
    "\N{OPTICAL DISC}": 1,
    "\N{FISHING POLE AND FISH}": 2,
    "\N{FISH}": 2,
    "\N{SNAIL}": 2,
    "\N{SHRIMP}": 2,
    "\N{CRAB}": 2,
    "\N{TROPICAL FISH}": 5,
    "\N{BLOWFISH}": 5,
    "\N{SQUID}": 5,
    "\N{TURTLE}": 8,
    "\N{OCTOPUS}": 8,
    "\N{LOBSTER}": 8,
    "\N{SHARK}": 10
}

# Fortune teller

FORTUNE_ENABLED: bool = cfg["fortune"]["enabled"]
FORTUNE_USE_PER: int = cfg["fortune"]["use_per"]
FORTUNE_USE_RATE: int = cfg["fortune"]["use_rate"]
FORTUNE_USE_VALUE: int = cfg["fortune"]["use_value"]

# Strength test

STRENGTH_ENABLED: bool = cfg["strength"]["enabled"]
STRENGTH_USE_PER: int = cfg["strength"]["use_per"]
STRENGTH_USE_RATE: int = cfg["strength"]["use_rate"]
STRENGTH_BONUS_VALUE: int = cfg["strength"]["bonus_value"]
STRENGTH_MAX_VALUE: int = cfg["strength"]["max_value"]

# Wheel

WHEEL_ENABLED: bool = cfg["wheel"]["enabled"]
WHEEL_USE_PER: int = cfg["wheel"]["use_per"]
WHEEL_USE_RATE: int = cfg["wheel"]["use_rate"]
WHEEL_WIN_CHANCE: float = cfg["wheel"]["win_chance"]

# Crystal ball

CRYSTALBALL_ENABLED: bool = cfg["crystalball"]["enabled"]

# Shop

SHOP_ROLE_LIST: List[dict] = sorted(cfg["shop"]["role_list"], key=lambda rd: rd.get("cost"))

