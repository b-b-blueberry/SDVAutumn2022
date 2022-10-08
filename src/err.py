# SDVAutumn2022
# err.py
# Written by blueberry et al., 2022
# https://github.com/StardewValleyDiscord/SDVAutumn2022

from datetime import datetime


def log(error: Exception) -> None:
    print("[{0}]\t{1}".format(
        datetime.now(),
        error))
