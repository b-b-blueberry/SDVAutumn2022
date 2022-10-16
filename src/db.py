# SDVAutumn2022
# db.py
# Written by blueberry et al., 2022
# https://github.com/StardewValleyDiscord/SDVAutumn2022

import sqlite3
from sqlite3 import Connection
from typing import List, Tuple, Optional

from config import PATH_DATABASE, STARTING_BALANCE


# Constant values


# Guild entries
TABLE_GUILDS: str = "GUILDS"
KEY_GUILD_ID: str = "ID"
KEY_GUILD_SHOP_ID: str = "SHOP_ID"
KEY_GUILD_EARNED: str = "EARNED"

# User entries
TABLE_USERS: str = "USERS"
KEY_USER_ID: str = "ID"
KEY_USER_BALANCE: str = "BALANCE"


# Utility methods


def setup():
    """
    Generates database with required tables.
    """
    db: Connection = sqlite3.connect(PATH_DATABASE)
    queries: List[str] = [
        # Global values
        f"CREATE TABLE IF NOT EXISTS {TABLE_GUILDS} ({KEY_GUILD_ID} INT PRIMARY KEY, {KEY_GUILD_SHOP_ID} INT, {KEY_GUILD_EARNED} INT)",
        # User values
        f"CREATE TABLE IF NOT EXISTS {TABLE_USERS} ({KEY_USER_ID} INT PRIMARY KEY, {KEY_USER_BALANCE} INT)"
    ]
    for query in queries:
        db.execute(query)
    db.commit()
    db.close()

def _db_read(_query: [tuple, str]) -> any:
    """
    Helper function to perform database reads.
    """
    sqlconn = sqlite3.connect(PATH_DATABASE)
    results: any
    if isinstance(_query, tuple):
        results = sqlconn.execute(*_query).fetchall()
    else:
        results = sqlconn.execute(_query).fetchone()
    sqlconn.close()
    return results

def _db_write(_query: [Tuple[str, list], str]):
    """
    Helper function to perform database writes.
    """
    sqlconn = sqlite3.connect(PATH_DATABASE)
    sqlconn.execute(*_query) if isinstance(_query, tuple) else sqlconn.execute(_query)
    sqlconn.commit()
    sqlconn.close()


# Guild queries


def get_guild_earnings(guild_id: int) -> int:
    """
    Gets the total earned in the current guild.
    """
    query: tuple = (f"SELECT {KEY_GUILD_EARNED} FROM {TABLE_GUILDS} WHERE {KEY_GUILD_ID}=?", [guild_id])
    guild = _db_read(query)
    return guild[0][0] if guild and guild[0] and guild[0][0] else 0

def set_guild_earnings(guild_id: int, value: int) -> int:
    """
    Updates the guild's total earnings value.
    :returns: Global earnings after changes.
    """
    message_id: int = get_shop_message_id(guild_id=guild_id)
    query: tuple = (f"REPLACE INTO {TABLE_GUILDS} ({KEY_GUILD_ID}, {KEY_GUILD_SHOP_ID}, {KEY_GUILD_EARNED}) VALUES (?, ?, ?)", [guild_id, message_id, value])
    _db_write(query)
    return get_guild_earnings(guild_id=guild_id)

def get_shop_message_id(guild_id: int) -> Optional[int]:
    """
    Gets the shop message ID for the current guild.
    """
    query: tuple = (f"SELECT {KEY_GUILD_SHOP_ID} FROM {TABLE_GUILDS} WHERE {KEY_GUILD_ID}=?", [guild_id])
    found_id = _db_read(query)
    return found_id[0][0] if found_id and found_id[0] else None

def set_shop_message_id(guild_id: int, message_id: int) -> None:
    """
    Updates a guild's shop message ID.
    """
    earnings: int = get_guild_earnings(guild_id=guild_id)
    query: tuple = (f"REPLACE INTO {TABLE_GUILDS} ({KEY_GUILD_ID}, {KEY_GUILD_SHOP_ID}, {KEY_GUILD_EARNED}) VALUES (?, ?, ?)", [guild_id, message_id, earnings])
    _db_write(query)


# User queries


def get_balance_for(user_id: int) -> int:
    """
    Gets the balance database entry for a given user.
    """
    query: tuple = (f"SELECT {KEY_USER_BALANCE} FROM {TABLE_USERS} WHERE {KEY_USER_ID}=?", [user_id])
    user = _db_read(query)

    if not user:
        return STARTING_BALANCE
    else:
        return user[0][0] if user and user[0] else None

def set_balance_for(user_id: int, value: int) -> int:
    """
    Updates a user's balance value.
    """
    query: tuple = (f"REPLACE INTO {TABLE_USERS} ({KEY_USER_ID}, {KEY_USER_BALANCE}) VALUES (?, ?)", [user_id, value])
    _db_write(query)
    return get_balance_for(user_id=user_id)
