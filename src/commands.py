# SDVAutumn2022
# commands.py
# Written by blueberry et al., 2022
# https://github.com/StardewValleyDiscord/SDVAutumn2022

import datetime
import logging
import random
from importlib import reload
from math import ceil, floor
from typing import Optional, List, Any, Dict

from discord import Reaction, User, Message, Emoji, utils, Interaction, Role, Guild, ButtonStyle, Member, TextChannel, \
    AllowedMentions, Embed
from discord.abc import GuildChannel
from discord.ext import commands
from discord.ext.commands import Cog, Context, BucketType, UserConverter, BadArgument, CommandOnCooldown, Bot, \
    MissingRequiredArgument
from discord.ui import View, Button

import config
import strings
import db
from config import FISHING_SCOREBOARD, ROLE_HELPER, ROLE_ADMIN, FISHING_BONUS_VALUE, FISHING_BONUS_CHANCE, \
    FISHING_HIGH_VALUE
from utils import check_roles, requires_admin, get_guild_message, query_channel

"""
Contents:
    SCommands
        Classes
            SShopView
            SShopButton
            SResponse
        Init
        Command utils
        Default user commands
        Admin commands
        Command implementations
        Event implementations
        Event listeners
    Discord.py boilerplate
"""


# Commands


class SCommands(Cog, name=config.COG_COMMANDS):
    # Classes

    class SShopView(View):
        """
        Component view for a button-based shop menu to exchange balance for bonuses.
        """

        ROW_LEN: int = 4

        def __init__(self, guild: Guild, bot: Bot):
            super().__init__(timeout=None)

            # Add shop buttons for up to 10 roles
            for (i, role_data) in enumerate(config.SHOP_ROLE_LIST):
                role_id: int = role_data.get("id")
                role: Role = guild.get_role(role_id)
                button: SCommands.SShopButton = SCommands.SShopButton(
                    row=int(i / SCommands.SShopView.ROW_LEN),
                    label=strings.get("shop_role_format").format(role.name, role_data.get("cost")),
                    custom_id=role_data.get("name"),
                    emoji=utils.get(bot.emojis, name=strings.get(f"emoji_{role_data.get('name')}")))
                self.add_item(item=button)

        async def interaction_check(self, interaction: Interaction, /) -> bool:
            """
            Override.

            Check before allowing a shop view interaction.
            """
            return True

    class SShopButton(Button):
        """
        Component button for a shop offer.
        """
        def __init__(self, custom_id: str, row: int, label: str, emoji: Emoji):
            super().__init__(
                style=ButtonStyle.blurple,
                label=label,
                emoji=emoji,
                row=row,
                custom_id=custom_id)

        async def callback(self, interaction: Interaction) -> Any:
            """
            Override.
            Handles interactions with shop buttons.
            """
            msg: str = None
            cost: int = 0
            balance_current: int = db.get_balance_for(user_id=interaction.user.id)

            # Handle different rows of buttons with different behaviours
            if self._is_role_button():
                cost = self._get_role_data().get("cost")
                if cost <= balance_current:
                    msg = await self._do_purchase_role(member=interaction.user)

            if not msg:
                # If no reply message is set, assume the user couldn't afford the shop offer
                msg = strings.random("shop_responses_poor").format(cost - balance_current)
            elif cost > 0:
                # Deduct cost from user's balance
                db.set_balance_for(user_id=interaction.user.id, value=balance_current - cost)
                msg_purchased: str = strings.random("shop_responses_purchase").format(cost, balance_current - cost)
                msg += f"\n{msg_purchased}"

            # Send user-only response depending on purchase and success
            await interaction.response.send_message(content=msg, ephemeral=True)

        async def _do_purchase_role(self, member: Member) -> str:
            """
            Removes all shop roles from a user, then awards them the shop role of their choosing.
            Does not check or deduct user's balance.
            :param member: User to award role to.
            :return: Confirmation message.
            """
            role_data: dict = self._get_role_data()
            roles_add: List[Role] = [utils.get(member.guild.roles, id=role_id)
                                     for role_id in [role_data.get("id"), config.ROLE_EVENT]]
            roles_remove: List[Role] = [utils.get(member.guild.roles, id=rd.get("id"))
                                        for rd in config.SHOP_ROLE_LIST
                                        if member.get_role(rd.get("id"))]
            log_reason: str = strings.get("log_role_purchase")

            # Remove other shop roles
            await member.remove_roles(*[role for role in roles_remove if role], reason=log_reason)
            # Add selected shop role, as well as generic event role
            await member.add_roles(*[role for role in roles_add if role], reason=log_reason)

            msg: str = strings.get("shop_responses_purchase_role")[role_data.get("response_index")]
            return msg

        def _get_role_data(self) -> dict:
            return next(rd for rd in config.SHOP_ROLE_LIST if rd.get("name") == self.custom_id)

        def _is_role_button(self) -> bool:
            return self.row < len(config.SHOP_ROLE_LIST) / SCommands.SShopView.ROW_LEN

    class SResponse:
        """
        Container for response messages and balance values from using a command.
        """
        def __init__(self, msg: str, value: int):
            self.msg: Optional[str] = msg
            """Response message string to be posted as a reply."""
            self.value: int = value
            """Value added to user's balance from within command."""

    # Init

    def __init__(self, bot: Bot):
        super().__init__()

        self.bot: Bot = bot
        """
        Main bot instance.
        """

        self.submission_session: List[int] = []
        """
        List of Discord message IDs that have been reacted to in the submission channels.
        
        A list sharing the lifetime of the bot session is fine here as messages sent outside of the session
        have no effect on reactions, so we don't need to check whether a reaction was already added.
        """

        self.fishing_session: Dict[int, List[int]] = {}
        """
        Map of Discord user IDs to message IDs they have reacted to in the fishing challenge.
        
        A map sharing the lifetime of the bot session is fine here as messages sent outside of the session
        have no effect on reactions, so we don't need to check whether a reaction was already added.
        """

    # Command utils

    def _log_admin(self, msg_key: str, user: User, value: Any = None):
        msg: str = strings.get(msg_key).format(
            user.name,
            user.discriminator,
            user.id,
            value)
        print(msg)
        logger: logging.Logger = logging.getLogger("discord")
        logger.log(level=logging.DEBUG, msg=msg)

    def _add_balance(self, guild_id: int, user_id: int, value: int) -> int:
        balance_current: int = db.get_balance_for(user_id=user_id)
        balance_current = db.set_balance_for(user_id=user_id, value=balance_current + value)
        if value > 0:
            self._add_earnings(guild_id=guild_id, value=value)
        return balance_current

    def _add_earnings(self, guild_id: int, value: int) -> int:
        earnings_current: int = db.get_guild_earnings(guild_id=guild_id)
        if value > 0:
            earnings_current = db.set_guild_earnings(guild_id=guild_id, value=earnings_current + value)
        return earnings_current

    # Default user commands

    @commands.command(name=strings.get("command_name_wheel"))
    @commands.cooldown(rate=config.WHEEL_USE_RATE, per=config.WHEEL_USE_PER, type=BucketType.user)
    async def cmd_wheel(self, ctx: Context, query: str, value: int) -> None:
        if not config.WHEEL_ENABLED:
            return
        msg: str
        balance_current: int = db.get_balance_for(user_id=ctx.author.id)
        if balance_current < value:
            msg = strings.random("shop_responses_poor").format(value - balance_current)
        else:
            query_clean: str = query.strip().lower()
            is_green: bool = query_clean.startswith("g") or query_clean.startswith("b")
            is_orange: bool = query_clean.startswith("o") or query_clean.startswith("r")
            if not is_green and not is_orange:
                msg = strings.random("wheel_responses_colour")
            else:
                response: SCommands.SResponse = self._do_wheel(guild_id=ctx.guild.id, user_id=ctx.author.id, value=value, is_green=is_green)
                response_key: str = 'balance_responses_added' if response.value > 0 else 'balance_responses_removed'
                if response.value != 0:
                    response.msg += f"\n{strings.random(response_key).format(response.value)}"
                msg = response.msg
        await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_fortune"))
    @commands.cooldown(rate=config.FORTUNE_USE_RATE, per=config.FORTUNE_USE_PER, type=BucketType.user)
    async def cmd_fortune(self, ctx: Context) -> None:
        if not config.FORTUNE_ENABLED:
            return
        response: SCommands.SResponse = self._do_fortune_command(user_id=ctx.author.id)
        if response.value != 0:
            response.msg += f"\n{strings.random('balance_responses_added').format(response.value)}"
        await ctx.reply(content=response.msg)

    @commands.command(name=strings.get("command_name_strength"))
    @commands.cooldown(rate=config.STRENGTH_USE_RATE, per=config.STRENGTH_USE_PER, type=BucketType.user)
    async def cmd_strength(self, ctx: Context) -> None:
        if not config.STRENGTH_ENABLED:
            return
        response: SCommands.SResponse = self._do_strength(guild_id=ctx.guild.id, user_id=ctx.author.id)
        if response.value > 0:
            response.msg += f"\n{strings.random('balance_responses_added').format(response.value)}"
        await ctx.reply(content=response.msg)

    @commands.command(name=strings.get("command_name_balance_get"))
    async def cmd_balance_get(self, ctx: Context, query: str = None) -> None:
        msg: str
        try:
            if not query:
                query = ctx.author.id
            user: User = await UserConverter().convert(
                ctx=ctx,
                argument=str(query).strip())
            response: SCommands.SResponse = self._do_balance_get(author=ctx.author, user=user)
            emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_shop"))
            msg = f"{emoji}\t{response.msg}"
        except BadArgument:
            msg = strings.get("commands_error_user")
        await ctx.reply(content=msg)

    # Admin commands

    @commands.command(name=strings.get("command_name_balance_add"))
    @commands.check(requires_admin)
    async def cmd_balance_set(self, ctx: Context, query: str, value: int) -> None:
        """
        Add a value to a given user's balance, deducting the same amount from the author's balance.
        :param ctx:
        :param query: Discord user ID, mention, or name to set balance for.
        :param value: Value to be added to balance.
        """
        msg: str
        try:
            user: User = await UserConverter().convert(
                ctx=ctx,
                argument=str(query).strip())
            response: SCommands.SResponse = self._do_balance_set(guild_id=ctx.guild.id, user_from=ctx.author, user_to=user, value=value)
            emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_shop"))
            msg = f"{emoji}\t{response.msg}"
        except BadArgument:
            msg = strings.get("commands_error_user")
        await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_award"))
    @commands.check(requires_admin)
    async def cmd_award(self, ctx: Context, query: str, value: int) -> None:
        """
        Add a value to a given user's balance.

        Negative values will be deducted from their balance.
        :param ctx:
        :param query: Discord user ID, mention, or name to set balance for.
        :param value: Value to be added to balance.
        """
        msg: str
        try:
            user: User = await UserConverter().convert(
                ctx=ctx,
                argument=str(query).strip())
            response: SCommands.SResponse = self._do_award(guild_id=ctx.guild.id, user=user, value=value)
            emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_shop"))
            msg = f"{emoji}\t{response.msg}"
        except BadArgument:
            msg = strings.get("commands_error_user")
        await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_earnings"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_earnings(self, ctx: Context, value: int = None) -> None:
        """
        Get or set the total earnings for this guild.

        Omitting value prints the current amount with no change to its value.
        :param ctx:
        :param value: Optional balance change to apply to the total earnings.
        """
        msg: str
        earnings_current: int = db.get_guild_earnings(guild_id=ctx.guild.id)
        if not value:
            # Omitting value will get current earnings
            msg = strings.get("commands_response_earnings_get").format(earnings_current)
        else:
            # Including value will change current earnings
            earnings_total: int = db.set_guild_earnings(guild_id=ctx.guild.id, value=earnings_current + value)
            msg = strings.get("commands_response_earnings_set").format(earnings_total, f"+{value}" if value >= 0 else value)
        await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_enabled"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_enabled(self, ctx: Context) -> None:
        msg = "\n".join([
            strings.get("commands_response_enable_submission").format(strings.on_off(config.SUBMISSION_ENABLED)),
            strings.get("commands_response_enable_fishing").format(strings.on_off(config.FISHING_ENABLED)),
            strings.get("commands_response_enable_fortune").format(strings.on_off(config.FORTUNE_ENABLED)),
            strings.get("commands_response_enable_strength").format(strings.on_off(config.STRENGTH_ENABLED)),
            strings.get("commands_response_enable_wheel").format(strings.on_off(config.WHEEL_ENABLED))
        ])
        await ctx.reply(content=strings.get("commands_response_enabled").format(msg))

    @commands.command(name=strings.get("command_name_enable_submission"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_enable_submission(self, ctx: Context, is_enabled: bool = None) -> None:
        if is_enabled is not None:
            config.SUBMISSION_ENABLED = is_enabled
            self._log_admin(msg_key="log_admin_enable_submission", user=ctx.author, value=strings.on_off(is_enabled))
        await ctx.reply(content=strings.get("commands_response_enable_submission").format(strings.on_off(config.SUBMISSION_ENABLED)))

    @commands.command(name=strings.get("command_name_enable_fishing"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_enable_fishing(self, ctx: Context, is_enabled: bool = None) -> None:
        if is_enabled is not None:
            config.FISHING_ENABLED = is_enabled
            self._log_admin(msg_key="log_admin_enable_fishing", user=ctx.author, value=strings.on_off(is_enabled))
        await ctx.reply(content=strings.get("commands_response_enable_fishing").format(strings.on_off(config.FISHING_ENABLED)))

    @commands.command(name=strings.get("command_name_enable_fortune"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_enable_fortune(self, ctx: Context, is_enabled: bool = None) -> None:
        if is_enabled is not None:
            config.FORTUNE_ENABLED = is_enabled
            self._log_admin(msg_key="log_admin_enable_fortune", user=ctx.author, value=strings.on_off(is_enabled))
        await ctx.reply(content=strings.get("commands_response_enable_fortune").format(strings.on_off(config.FORTUNE_ENABLED)))

    @commands.command(name=strings.get("command_name_enable_strength"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_enable_strength(self, ctx: Context, is_enabled: bool = None) -> None:
        if is_enabled is not None:
            config.STRENGTH_ENABLED = is_enabled
            self._log_admin(msg_key="log_admin_enable_strength", user=ctx.author, value=strings.on_off(is_enabled))
        await ctx.reply(content=strings.get("commands_response_enable_strength").format(strings.on_off(config.STRENGTH_ENABLED)))

    @commands.command(name=strings.get("command_name_enable_wheel"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_enable_wheel(self, ctx: Context, is_enabled: bool = None) -> None:
        if is_enabled is not None:
            config.WHEEL_ENABLED = is_enabled
            self._log_admin(msg_key="log_admin_enable_wheel", user=ctx.author, value=strings.on_off(is_enabled))
        await ctx.reply(content=strings.get("commands_response_enable_wheel").format(strings.on_off(config.WHEEL_ENABLED)))

    @commands.command(name=strings.get("command_name_enable_crystalball"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_enable_crystalball(self, ctx: Context, is_enabled: bool = None) -> None:
        if is_enabled is not None:
            config.CRYSTALBALL_ENABLED = is_enabled
            self._log_admin(msg_key="log_admin_enable_crystalball", user=ctx.author, value=strings.on_off(is_enabled))
        await ctx.reply(content=strings.get("commands_response_enable_crystalball").format(strings.on_off(config.CRYSTALBALL_ENABLED)))

    @commands.command(name=strings.get("command_name_sync"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_sync(self, ctx: Context) -> None:
        self._log_admin(msg_key="log_admin_sync", user=ctx.author)
        await self.bot.sync_guild(ctx.guild)
        await ctx.reply(content=strings.get("commands_response_sync"))

    @commands.command(name=strings.get("command_name_reload"), aliases=["z"], hidden=True)
    @commands.check(requires_admin)
    async def cmd_reload(self, ctx: Context) -> None:
        """
        Reloads the commands extension, reapplying code changes and reloading the strings data file.
        """
        self._log_admin(msg_key="log_admin_reload", user=ctx.author)
        await self.bot.reload_extension(name=config.PACKAGE_COMMANDS)
        await ctx.message.add_reaction(strings.emoji_confirm)

    @commands.command(name=strings.get("command_name_test_string"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_test_string(self, ctx: Context, string: str) -> None:
        """
        Test a given string without formatting.
        :param ctx:
        :param string: Key of string in strings data file.
        """
        msg: str = strings.get(string)
        await ctx.reply(content=strings.get("commands_response_test_string").format(string, msg)
                        if msg
                        else strings.get("error_string_not_found").format(string))

    @commands.command(name=strings.get("command_name_test_emoji"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_test_emoji(self, ctx: Context) -> None:
        """
        Test emoji availability and visibility.
        :param ctx:
        """
        msg: str = "\n".join([strings.get("commands_response_test_emoji_format").format(
            utils.get(self.bot.emojis, name=strings.get(e)),
            strings.get(e),
            e)
            for e in strings.get("emoji_list")])
        await ctx.reply(content=strings.get("commands_response_test_emoji").format(msg))

    @commands.command(name=strings.get("command_name_test_roles"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_test_roles(self, ctx: Context) -> None:
        """
        Test role availability and visibility.
        :param ctx:
        """
        msg: str = "\n".join([strings.get("commands_response_test_roles_format").format(
            utils.get(self.bot.emojis, name=strings.get(f"emoji_{rd.get('name')}")),
            ctx.guild.get_role(rd.get("id")).mention,
            rd.get("name"),
            rd.get("cost"))
            for rd in config.SHOP_ROLE_LIST])
        await ctx.reply(content=strings.get("commands_response_test_roles").format(msg))

    @commands.command(name=strings.get("command_name_test_fish"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_test_fish(self, ctx: Context) -> None:
        """
        Test fish emoji and scoring.
        :param ctx:
        """
        msg: str = "\n".join([strings.get("commands_response_test_fish_format").format(
            key if len(key) == 1 else utils.get(self.bot.emojis, name=key),
            config.FISHING_SCOREBOARD[key])
            for key in config.FISHING_SCOREBOARD.keys()])
        await ctx.reply(content=strings.get("commands_response_test_fish").format(msg))

    @commands.command(name=strings.get("command_name_message_send"))
    @commands.check(requires_admin)
    async def cmd_send_message(self, ctx: Context, query: str, *, content: str) -> None:
        """
        Sends a message in a given channel.
        :param ctx:
        :param query: Query for Discord channel to send message in.
        :param content: Message content to send.
        :return:
        """
        if not content:
            content = " "
        content = content[:2000]
        channel: GuildChannel = query_channel(guild=ctx.guild, query=query)
        if content and isinstance(channel, TextChannel):
            message: Message = await channel.send(content=content)
            msg = strings.get("commands_response_send_success").format(
                channel.mention,
                message.jump_url)
        else:
            msg = strings.get("commands_response_send_failure")
        await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_message_edit"))
    @commands.check(requires_admin)
    async def cmd_edit_message(self, ctx: Context, message_id: int, *, content: str) -> None:
        """
        Edits a message in the current guild.
        :param ctx:
        :param message_id: Discord message ID to edit.
        :param content: Message content to use.
        """
        if not content:
            content = " "
        content = content[:2000]
        msg: str
        message: Message = await get_guild_message(guild=ctx.guild, message_id=message_id)
        if content and message:
            await message.edit(content=content, embeds=message.embeds)
            msg = strings.get("commands_response_edit_success").format(
                message.channel.mention,
                message.jump_url)
        else:
            msg = strings.get("commands_response_edit_failure")
        await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_shop_update"))
    @commands.check(requires_admin)
    async def cmd_update_shop(self, ctx: Context) -> None:
        """
        Generates and sends persistent Shop message in the configured channel.
        """
        msg: str = await self._do_update_shop(ctx=ctx)
        await ctx.reply(content=msg)

    # Command implementations

    def _do_fortune_command(self, user_id: int) -> SResponse:
        """
        ???
        :param user_id: Discord user ID for a given user.
        """
        response: str = ""
        emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_fortune"))
        msg: str = f"{emoji}\t{response}"
        response: SCommands.SResponse = SCommands.SResponse(msg=msg, value=config.FORTUNE_USE_VALUE)
        return response

    def _do_strength(self, guild_id: int, user_id: int) -> SResponse:
        """
        Generate a message for a strength-test scenario and add value to user's balance.
        :param user_id: Discord user ID for a given user.
        """
        # Outcomes set is in ascending order, from the lowest value at 0 to the highest value at len
        outcomes: List[str] = strings.get("strength_responses_score")
        outcome_index: int = random.randint(0, len(outcomes))
        outcome_value: int = max(1, (floor(ceil(outcome_index) / len(outcomes) * config.STRENGTH_MAX_VALUE)))

        is_weak: bool = outcome_index == 0
        is_strong: bool = outcome_index == len(outcomes) - 1

        # Add value of outcome as a ratio of possible outcomes earned by this user to their balance
        balance_bonus: int = config.STRENGTH_BONUS_VALUE if is_weak or is_strong else 0
        balance_earned: int = outcome_value + balance_bonus
        self._add_balance(guild_id=guild_id, user_id=user_id, value=balance_earned)

        response: str = strings.get("strength_response_format").format(
            strings.random("strength_responses_start"),
            strings.random("strength_responses_hit"),
            strings.emoji_explosion,
            strings.random("strength_responses_end"),
            outcomes[outcome_index]
        )
        emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_strength"))
        msg: str = f"{emoji}\t{response}"
        if is_weak:
            msg += f"\n{strings.random('strength_responses_weak')}"
        elif is_strong:
            msg += f"\n{strings.random('strength_responses_strong')}"

        return SCommands.SResponse(msg=msg, value=balance_earned)

    def _do_wheel(self, guild_id: int, user_id: int, value: int, is_green: bool) -> SResponse:
        random_range: int = 100
        random_result: int = random.randint(0, random_range)
        is_win: bool = random_result < random_range * config.WHEEL_WIN_CHANCE

        # Add or remove from the user's balance
        balance_earned: int = value * (1 if is_win else -1)
        self._add_balance(guild_id=guild_id, user_id=user_id, value=balance_earned)

        # Send a reply with the matching colour set for a win or loss
        emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_wheel"))
        response_start: str = f"{emoji}\t{strings.random('wheel_responses_start')}"

        # Losses will show the response as if the opposite set landed
        response_key: str
        if is_green:
            response_key = "wheel_responses_win_a" if is_win else "wheel_responses_lose_b"
        else:
            response_key = "wheel_responses_win_b" if is_win else "wheel_responses_lose_a"
        response: str = strings.random(response_key)
        msg: str = strings.get("wheel_response_format").format(response_start, response)

        return SCommands.SResponse(msg=msg, value=balance_earned)

    def _do_balance_get(self, author: User, user: User) -> SResponse:
        """
        Gets a user's balance.
        :param author: User checking balance.
        :param user: User to check.
        """
        balance: int = db.get_balance_for(user_id=user.id)
        msg_balance_key: str = "balance_responses_other" if author.id != user.id \
            else "balance_responses_none" if balance < 1 \
            else "balance_responses_one" if balance == 1 \
            else "balance_responses_many"
        msg: str = strings.random(msg_balance_key).format(balance, user.mention)
        return SCommands.SResponse(msg=msg, value=balance)

    def _do_balance_set(self, guild_id: int, user_from: User, user_to: User, value: int) -> SResponse:
        """
        Sets balance for a user.
        :param user_from: User donating balance.
        :param user_to: User receiving donation.
        :param value: Value to be added to user's balance.
        """
        balance_from: int = db.get_balance_for(user_id=user_from.id)
        balance_donated: int = min(balance_from, value)
        is_negative: bool = balance_donated < 1

        if user_from.id == user_to.id or value < 1:
            raise BadArgument()
        elif is_negative:
            value = 0
        else:
            # Add balance to target user
            self._add_balance(guild_id=guild_id, user_id=user_to.id, value=balance_donated)
            # Deduct balance from self user
            self._add_balance(guild_id=guild_id, user_id=user_from.id, value=-balance_donated)

        msg_balance_key: str = "balance_responses_too_low" if is_negative else "balance_responses_donated"
        msg: str = strings.random(msg_balance_key).format(balance_donated, balance_from, user_to.mention, db.get_balance_for(user_id=user_to.id))
        return SCommands.SResponse(msg=msg, value=value)

    def _do_award(self, guild_id: int, user: User, value: int) -> SResponse:
        """
        Adds a value to a user's balance.
        :param user: User receiving donation.
        :param value: Value to be added to user's balance.
        """
        # Add to user's balance
        self._add_balance(guild_id=guild_id, user_id=user.id, value=value)

        msg: str = strings.random("award_responses").format(value, user.mention)
        return SCommands.SResponse(msg=msg, value=value)

    async def _do_update_shop(self, ctx: Context) -> str:
        message_id: int = db.get_shop_message_id(guild_id=ctx.guild.id)
        emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_shop"))
        msg_roles: str = "\n".join([strings.get("message_shop_role").format(
            utils.get(self.bot.emojis, name=strings.get(f"emoji_{role_data.get('name')}")),
            ctx.guild.get_role(role_data.get("id")).mention,
            role_data.get("cost")
        ) for role_data in config.SHOP_ROLE_LIST])
        msg: str
        shop_title: str = strings.get("message_shop_title").format(strings.emoji_shop)
        shop_body: str = strings.get("message_shop_body").format(msg_roles, emoji)
        embed: Embed = Embed(
            colour=ctx.guild.get_member(self.bot.user.id).colour,
            title=shop_title,
            description=shop_body)
        embed.set_thumbnail(url=emoji.url)
        view: View = SCommands.SShopView(guild=ctx.guild, bot=self.bot)
        channel: TextChannel = self.bot.get_channel(config.CHANNEL_SHOP)
        message: Message
        if message_id:
            message = await channel.get_partial_message(message_id).edit(content=None, embed=embed, view=view)
            msg = strings.get("commands_response_edit_success").format(
                message.channel.mention,
                message.jump_url)
        else:
            message = await channel.send(content=None, embed=embed, view=view)
            db.set_shop_message_id(guild_id=ctx.guild.id, message_id=message.id)
            msg = strings.get("commands_response_send_success").format(
                channel.mention,
                message.jump_url)
        return msg

    # Event implementations

    async def _do_verification(self, reaction: Reaction, user: User) -> Optional[str]:
        """
        Staff reactions to posts with attachments in the submissions channel will add to the author's balance.
        :param reaction: Reaction instance for a given emoji on the message.
        :param user: User reacting to the message.
        """
        if check_roles(user=user, role_ids=[ROLE_ADMIN, ROLE_HELPER]) \
                and reaction.message.id not in self.submission_session:
            if any(reaction.message.attachments) or any(reaction.message.embeds):
                self.submission_session.append(reaction.message.id)
                is_art: bool = reaction.message.channel.id == config.CHANNEL_ART
                balance_earned: int = config.SUBMISSION_ART_VALUE if is_art else config.SUBMISSION_FOOD_VALUE
                self._add_balance(guild_id=reaction.message.guild.id, user_id=user.id, value=balance_earned)
                msg_key: str = "submission_responses_art" if is_art else "submission_responses_food"
                msg: str = strings.random(msg_key).format(balance_earned)
                return msg

    async def _do_fishing(self, reaction: Reaction, user: User) -> Optional[SResponse]:
        """
        Adds to a user's balance some value based on the fish emoji in a message they reacted to.
        :param reaction: Reaction instance for a given emoji on the message.
        :param user: User reacting to the message.
        """
        # Check fishing session to prevent users adding multiple reactions to the same message to cheat their balance
        fishing_user: List[int] = self.fishing_session.get(user.id, [])
        if reaction.message.id in fishing_user:
            return

        msg: str
        balance_earned: int = 0
        balance_bonus: int = 0

        # Save interaction to fishing session
        fishing_user.append(reaction.message.id)
        self.fishing_session[user.id] = fishing_user

        # Check if catch period has expired, converting to timezone-unaware times
        time_now = datetime.datetime.now(tz=datetime.timezone.utc)
        time_msg = reaction.message.created_at
        time_period = datetime.timedelta(seconds=config.FISHING_DURATION_SECONDS)
        time_delta = time_now - time_msg
        if time_delta > time_period:
            msg = strings.random("fishing_responses_timeout")
        else:
            # Sum the value of fish caught in this message
            fish_caught: List[int] = [FISHING_SCOREBOARD[key] * reaction.message.content.count(key)
                                      for key in FISHING_SCOREBOARD.keys()]
            fish_value: int = sum(fish_caught)
            is_catch: bool = fish_value > 0

            if is_catch:
                # Add value of fish caught by this user to their balance
                random_range: int = 100
                random_result: int = random.randint(0, random_range)
                if random_result < FISHING_BONUS_CHANCE * random_range:
                    balance_bonus = FISHING_BONUS_VALUE
                balance_earned = fish_value + balance_bonus
                self._add_balance(guild_id=reaction.message.guild.id, user_id=user.id, value=balance_earned)

            # Abandon the catch if message had no fish emoji
            if not any(fish_caught):
                return

            # Generate a reply message based on number or value of fish caught
            response_key: str = "fishing_responses_none" if not is_catch \
                else "fishing_responses_value" if fish_value >= FISHING_HIGH_VALUE \
                else "fishing_responses_one" if len([count for count in fish_caught if count > 0]) == 1 \
                else "fishing_responses_many"
            msg = strings.random(response_key)
            if balance_bonus > 0:
                msg += f"\n{strings.random('fishing_responses_bonus')}"

        emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_fishing"))
        msg = f"{emoji}{user.mention}\t{msg}"
        response: SCommands.SResponse = SCommands.SResponse(msg=msg, value=balance_earned)

        return response

    async def _do_fortune_message(self, message: Message) -> Optional[SResponse]:
        """
        Generate a message as a reply to any users asking a generic question in visible text channels.
        :param message: Discord message to parse and create a reply to.
        """
        msg: str
        response: Optional[SCommands.SResponse] = None
        # Find questions in the message
        qi: int
        try:
            qi = message.content.index("?")
        except ValueError:
            return
        # Flatten out the question into lowercase chars for some simple stupid seed
        question: str = message.content[:qi]
        chars: str = "".join([c for c in question if c.isalnum()]).lower() if question else None
        # Ignore questions expecting a detailed answer
        if chars and all([not chars.startswith(s) for s in ["why", "who", "what", "where", "how"]]):
            # We skip the usual strings random call to use a random seeded by the question
            response: str = random.Random(chars).choice(strings.get("fortune_responses"))
            emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_fortune"))
            msg = f"{emoji}\t{response}"
            response = SCommands.SResponse(msg=msg, value=0)
        return response

    # Event listeners

    async def on_message(self, message: Message) -> None:
        if message.author.bot:
            return

        # Do bot responses on user messages in command channels
        if config.CRYSTALBALL_ENABLED and message.channel.id in config.CHANNEL_COMMANDS:
            response: Optional[SCommands.SResponse] = await self._do_fortune_message(message=message)
            if response:
                await message.reply(content=response.msg)

    async def on_reaction_add(self, reaction: Reaction, user: User) -> None:
        if reaction.message.author.bot or user.bot:
            return

        # Do staff verification on user messages in submission channels
        if config.SUBMISSION_ENABLED and reaction.message.channel.id in [config.CHANNEL_ART, config.CHANNEL_FOOD]:
            msg: str = await self._do_verification(reaction=reaction, user=user)
            if msg:
                await reaction.message.add_reaction(strings.emoji_confirm)
                emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_submissions"))
                msg = f"{emoji}\t{msg}"
                await reaction.message.reply(content=msg)

        # Do fishing responses on staff messages in any channels
        if config.FISHING_ENABLED and check_roles(user=reaction.message.author, role_ids=[ROLE_ADMIN, ROLE_HELPER]):
            response: Optional[SCommands.SResponse] = await self._do_fishing(reaction=reaction, user=user)
            if response:
                channel: TextChannel = self.bot.get_channel(config.CHANNEL_FISHING)
                if response.value > 0:
                    response.msg += f"\n{strings.random('balance_responses_added').format(response.value)}"
                await channel.send(content=response.msg, allowed_mentions=AllowedMentions(users=True))

    async def on_command_error(self, ctx: Context, error: Exception) -> None:
        msg: str = None
        if ctx.command is None:
            msg = strings.get("error_command_not_found")
        else:
            # Makes perfect sense
            cmd: str = ctx.command.name
            cmd_internal_name: str = [s for s in strings.get("command_list") if strings.get(s) == cmd][0].split("_", 2)[-1]
            if isinstance(error, CommandOnCooldown):
                msg = strings.random(f"{cmd_internal_name}_responses_cooldown")
            if isinstance(error, MissingRequiredArgument):
                msg = strings.random(f"{cmd_internal_name}_responses_params")
            emoji_name: str = strings.get(f"emoji_{cmd_internal_name}")
            emoji: Emoji = utils.get(self.bot.emojis, name=emoji_name)
            if msg and emoji:
                msg = f"{emoji}\t{msg}"
        if msg:
            await ctx.reply(content=msg)


# Discord.py boilerplate


async def setup(bot: Bot):
    # Add cog
    cog: SCommands = SCommands(bot=bot)
    await bot.add_cog(cog)

    # Add event listeners
    bot.add_listener(cog.on_message, name="on_message")
    bot.add_listener(cog.on_reaction_add, name="on_reaction_add")
    bot.add_listener(cog.on_command_error, name="on_command_error")

    # Load data
    bot.reload_strings()
    reload(strings)
    reload(utils)
