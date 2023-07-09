# SDVAutumn2022
# strings.py
# Written by blueberry et al., 2022
# https://github.com/StardewValleyDiscord/SDVAutumn2022

"""
References:
    http://www.unicode.org/Public/UCD/latest/ucd/NamesList.txt
    https://unicode.org/emoji/charts/full-emoji-list.html
"""

import json
import random as rand
from typing import Optional, Any

from config import PATH_STRINGS

with open(file=PATH_STRINGS, mode="r", encoding="utf8") as strings_file:
    _data = json.load(strings_file)

def get(__name: str) -> Optional[any]:
    return _data.get(__name)

def random(__name: str) -> Optional[str]:
    return rand.choice(_data.get(__name))

def on_off(_value: Optional[Any]) -> str:
    return _data.get("on" if _value else "off")


emoji_confirm = "\N{WHITE HEAVY CHECK MARK}"
emoji_cancel = "\N{CROSS MARK}"
emoji_cancel_inverted = "\N{HEAVY MULTIPLICATION X}"
emoji_error = "\N{CROSS MARK}"
emoji_exclamation = "\N{WHITE EXCLAMATION MARK ORNAMENT}"
emoji_question = "\N{WHITE QUESTION MARK ORNAMENT}"
emoji_connection = "\N{ANTENNA WITH BARS}"
emoji_shop = "\N{SHOPPING BAGS}"
emoji_house = "\N{DERELICT HOUSE BUILDING}"
emoji_memo = "\N{MEMO}"
emoji_star = "\N{WHITE MEDIUM STAR}"
emoji_coin = "🪙"
