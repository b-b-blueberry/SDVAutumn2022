# SDVAutumn2022
# db.py
# Written by blueberry et al., 2022
# https://github.com/StardewValleyDiscord/SDVAutumn2022

import sqlite3
from sqlite3 import Connection
from typing import List, Tuple

from config import PATH_DATABASE, STARTING_BALANCE


# Constant values

# Text
LIST_DELIMITER: str = " "

# Guild entries
TABLE_GUILDS: str = "GUILDS"
KEY_GUILD_ID: str = "ID"
KEY_GUILD_SHOP_ID: str = "SHOP_ID"
KEY_GUILD_EARNED: str = "EARNED"

# User entries
TABLE_USERS: str = "USERS"
KEY_USER_ID: str = "ID"
KEY_USER_EARNED: str = "EARNED"
KEY_USER_BALANCE: str = "BALANCE"
KEY_USER_PICROSS_COUNT: str = "PICROSS_COUNT"
KEY_USER_SUBMITTED_CHANNELS: str = "SUBMITTED_CHANNELS"


# Data models


class DBGuild:
    def __init__(
            self,
            guild_id: int,
            earnings: int = 0,
            shop_message_id: int = None
    ):
        self.guild_id = guild_id
        self.earnings = earnings
        self.shop_message_id = shop_message_id

    @staticmethod
    def query_create() -> str:
        return "CREATE TABLE IF NOT EXISTS {0} ({1} INT PRIMARY KEY, {2} INT, {3} INT)".format(
            TABLE_GUILDS,
            KEY_GUILD_ID,
            KEY_GUILD_EARNED,
            KEY_GUILD_SHOP_ID,
        )

    @staticmethod
    def query_get(guild_id: int) -> tuple:
        return (
            "SELECT * FROM {0} WHERE {1} = ?"
            .format(
                TABLE_GUILDS,
                KEY_GUILD_ID
            ),
            [
                guild_id
            ])

    @staticmethod
    def query_set(entry: "DBGuild") -> tuple:
        args: List = [
                entry.guild_id,
                entry.earnings,
                entry.shop_message_id
            ]
        return (
            "REPLACE INTO {0} ({1}, {2}, {3}) VALUES ({4})"
            .format(
                TABLE_GUILDS,
                KEY_GUILD_ID,
                KEY_GUILD_EARNED,
                KEY_GUILD_SHOP_ID,
                ", ".join("?" * len(args))
            ), args)

    @staticmethod
    def from_raw(entry: list) -> "DBGuild":
        """
        Creates a DBGuild instance from a database entry with default values.
        """
        return DBGuild(
            guild_id=entry[0],
            earnings=entry[1],
            shop_message_id=entry[2]
        )


class DBUser:
    def __init__(
            self,
            user_id: int,
            earnings: int = 0,
            balance: int = STARTING_BALANCE,
            picross_count: int = 0,
            submitted_channels: List[int] = None
    ):
        self.user_id = user_id
        self.earnings = earnings
        self.balance = balance
        self.picross_count = picross_count
        self.submitted_channels = submitted_channels or []

    @staticmethod
    def query_create() -> str:
        return "CREATE TABLE IF NOT EXISTS {0} ({1} INT PRIMARY KEY, {2} INT, {3} INT, {4} INT, {5} TEXT)".format(
            TABLE_USERS,
            KEY_USER_ID,
            KEY_USER_EARNED,
            KEY_USER_BALANCE,
            KEY_USER_PICROSS_COUNT,
            KEY_USER_SUBMITTED_CHANNELS
        )

    @staticmethod
    def query_get(user_id: int) -> tuple:
        return (
            "SELECT * FROM {0} WHERE {1} = ?"
            .format(
                TABLE_USERS,
                KEY_USER_ID
            ),
            [
                user_id
            ])

    @staticmethod
    def query_set(entry: "DBUser") -> tuple:
        args: List = [
                entry.user_id,
                entry.earnings,
                entry.balance,
                entry.picross_count,
                LIST_DELIMITER.join([str(i) for i in entry.submitted_channels])
            ]
        return (
            "REPLACE INTO {0} ({1}, {2}, {3}, {4}, {5}) VALUES ({6})"
            .format(
                TABLE_USERS,
                KEY_USER_ID,
                KEY_USER_EARNED,
                KEY_USER_BALANCE,
                KEY_USER_PICROSS_COUNT,
                KEY_USER_SUBMITTED_CHANNELS,
                ", ".join("?" * len(args))
            ), args)

    @staticmethod
    def from_raw(entry: list) -> "DBUser":
        """
        Creates a DBUser instance from a database entry.
        """
        return DBUser(
            user_id=entry[0],
            earnings=entry[1],
            balance=entry[2],
            picross_count=entry[3],
            submitted_channels=[int(s) for s in entry[4].split(LIST_DELIMITER) if s.isnumeric()]
        )


# Utility methods


def setup():
    """
    Generates database with required tables.
    """
    db: Connection = sqlite3.connect(PATH_DATABASE)
    queries: List[str] = [
        DBGuild.query_create(),
        DBUser.query_create()
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


def get_guild(guild_id: int) -> DBGuild:
    """
    Gets the database entry for a given user.
    """
    guild_raw: list = _db_read(DBGuild.query_get(guild_id=guild_id))
    return DBGuild.from_raw(guild_raw[0]) if guild_raw and guild_raw[0] else DBGuild(guild_id=guild_id)

def update_guild(entry: DBGuild) -> None:
    """
    Updates a user's database entry.
    """
    _db_write(DBGuild.query_set(entry=entry))


# User queries


def get_user(user_id: int) -> DBUser:
    """
    Gets the database entry for a given user.
    """
    user_raw: list = _db_read(DBUser.query_get(user_id=user_id))
    return DBUser.from_raw(user_raw[0]) if user_raw and user_raw[0] else DBUser(user_id=user_id)

def update_user(entry: DBUser) -> None:
    """
    Updates a user's database entry.
    """
    _db_write(DBUser.query_set(entry=entry))
