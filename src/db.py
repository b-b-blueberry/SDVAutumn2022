# SDVAutumn2022
# db.py
# Written by blueberry et al., 2022
# https://github.com/StardewValleyDiscord/SDVAutumn2022

import sqlite3
from sqlite3 import Connection
from typing import List, Tuple, Optional

from config import PATH_DATABASE, STARTING_BALANCE


# Constant values


# Global entries
from src import strings

TABLE_GLOBAL: str = "GLOBAL"
KEY_GLOBAL_SHOP_ID: str = "SHOP_ID"
KEY_GLOBAL_EARNED: str = "EARNED"

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
        f"CREATE TABLE IF NOT EXISTS {TABLE_GLOBAL} ({KEY_GLOBAL_SHOP_ID} INT, {KEY_GLOBAL_EARNED} INT)",
        # User values
        f"CREATE TABLE IF NOT EXISTS {TABLE_USERS} ({KEY_USER_ID} INT PRIMARY KEY, {KEY_USER_BALANCE} INT)"
    ]
    for query in queries:
        db.execute(query)
    db.commit()
    db.close()

def _db_read(query: [tuple, str]) -> any:
    """
    Helper function to perform database reads.
    """
    sqlconn = sqlite3.connect(PATH_DATABASE)
    results: any
    if isinstance(query, tuple):
        results = sqlconn.execute(*query).fetchall()
    else:
        results = sqlconn.execute(query).fetchone()
    sqlconn.close()
    return results

def _db_write(query: [Tuple[str, list], str]):
    """
    Helper function to perform database writes.
    """
    sqlconn = sqlite3.connect(PATH_DATABASE)
    sqlconn.execute(*query) if isinstance(query, tuple) else sqlconn.execute(query)
    sqlconn.commit()
    sqlconn.close()


# Guild queries


def get_global_earnings() -> int:
    """
    Gets the total earned in the current guild.
    """
    guild = _db_read(f"SELECT {KEY_GLOBAL_EARNED} FROM {TABLE_GLOBAL}")
    return guild[0] if guild and guild[0] else 0

def set_global_earnings(value: int) -> int:
    """
    Updates the guild's total earnings value.
    """
    query: tuple = (f"REPLACE INTO {TABLE_GLOBAL} ({KEY_GLOBAL_EARNED}) VALUES (?)", [value])
    _db_write(query)
    return get_global_earnings()

def get_shop_message_id() -> Optional[int]:
    """
    Gets the shop message ID for the current guild.
    """
    found_id = _db_read(f"SELECT {KEY_GLOBAL_SHOP_ID} FROM {TABLE_GLOBAL}")
    return found_id[0] if found_id else None

def set_shop_message_id(message_id: int) -> None:
    """
    Updates a guild's shop message ID.
    """
    query: tuple = (f"REPLACE INTO {TABLE_GLOBAL} ({KEY_GLOBAL_SHOP_ID}) VALUES (?)", [message_id])
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
        return user[0][0]

def set_balance_for(user_id: int, value: int) -> int:
    """
    Updates a user's balance value.
    """
    query: tuple = (f"REPLACE INTO {TABLE_USERS} ({KEY_USER_ID}, {KEY_USER_BALANCE}) VALUES (?, ?)", [user_id, value])
    _db_write(query)
    return get_balance_for(user_id=user_id)
