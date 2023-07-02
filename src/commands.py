# SDVAutumn2022
# commands.py
# Written by blueberry et al., 2022
# https://github.com/StardewValleyDiscord/SDVAutumn2022

import json
import logging
import os
import re
from datetime import datetime
from importlib import reload
from io import StringIO
from typing import Optional, List, Any, Dict, Tuple, Union

import discord.utils
from discord import User, Message, Emoji, utils, Interaction, Role, Guild, ButtonStyle, Member, TextChannel, Embed, \
    HTTPException, ui, File, Attachment, Colour
from discord.abc import GuildChannel
from discord.ext import commands
from discord.ext.commands import Cog, Context, UserConverter, BadArgument, CommandOnCooldown, Bot, \
    MissingRequiredArgument
from discord.ui import View, Button

import config
import strings
import db
from utils import requires_admin, get_guild_message, query_channel, CheckFailureQuietly, check_roles

"""
Contents:
    Commands
        SCommands
            Classes
                SShopView
                SShopButton
                SResponse
                SVerifyButton
                SVerifyView
            Init
            Default user commands
            Admin commands
            Command implementations
            Event implementations
            Event listeners
    Command utils
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
            for i, role_data in enumerate(config.SHOP_ROLE_LIST):
                role_id: int = role_data.get("id")
                role: Role = guild.get_role(role_id)
                button: SCommands.SShopButton = SCommands.SShopButton(
                    row=int(i / SCommands.SShopView.ROW_LEN),
                    label=strings.get("shop_role_format").format(role.name, role_data.get("cost")),
                    custom_id=role_data.get("name"),
                    emoji=utils.get(bot.emojis, name=strings.get(f"emoji_hat_{role_data.get('name')}")))
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
            user_entry: db.DBUser = db.get_user(user_id=interaction.user.id)

            # Handle different rows of buttons with different behaviours
            if self._is_role_button():
                cost = self._get_role_data().get("cost")
                if cost <= user_entry.balance:
                    msg = await self._do_purchase_role(member=interaction.user)

            if not msg:
                # If no reply message is set, assume the user couldn't afford the shop offer
                msg = strings.random("shop_responses_poor").format(cost - user_entry.balance)
            elif cost > 0:
                # Deduct cost from user's balance
                user_entry.balance -= cost
                db.update_user(entry=user_entry)
                msg_purchased: str = strings.random("shop_responses_purchase").format(cost, user_entry.balance)
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

    class SVerifyRejectButton(ui.Button):
        def __init__(self, *, submission_author: User, submission_channel: TextChannel):
            self.submission_channel: TextChannel = submission_channel
            self.submission_author: User = submission_author

            super().__init__(
                style=ButtonStyle.danger,
                emoji=strings.emoji_cancel_inverted
            )

        async def callback(self, interaction: Interaction):
            # Update verify message
            embed: Embed = interaction.message.embeds[0]
            embed.description = strings.get("submission_verify_cancel").format(
                embed.description,
                interaction.user.mention,
                self.submission_author.mention,
                strings.emoji_cancel
            )
            await self.view.fold_embed(interaction=interaction, embed=embed)

            # Send rejection message in secret submission channel
            await self.submission_channel.send(content=strings.get("submission_verify_response").format(
                self.submission_author.mention,
                strings.emoji_cancel
            ))

    class SVerifyButton(ui.Button):
        def __init__(self, *, award_index: int, submission_author: User, submission_channel: TextChannel):
            self.submission_channel: TextChannel = submission_channel
            self.submission_author: User = submission_author
            self.award_index: int = award_index
            award_data: dict = self.get_award_data()

            super().__init__(
                label=str(award_data["value"]),
                style=ButtonStyle.primary,
                emoji=strings.emoji_coin
            )

        async def callback(self, interaction: Interaction):
            guild_entry: db.DBGuild = db.get_guild(guild_id=interaction.guild_id)
            user_entry: db.DBUser = db.get_user(user_id=self.submission_author.id)

            # Use face value for award for consistency, otherwise query config value
            award_value: int = int(self.label) if str.isnumeric(self.label) else self.get_award_data()["value"]

            # Award user with tokens
            _add_balance(guild_entry=guild_entry, user_entry=user_entry, value=award_value)

            # Update verify message
            embed: Embed = interaction.message.embeds[0]
            user_entry: db.DBUser = db.get_user(user_id=self.submission_author.id)
            user_entry.picross_count += 1
            db.update_user(user_entry)
            embed.description = strings.get("submission_verify_success").format(
                embed.description,
                interaction.user.mention,
                self.submission_author.mention,
                award_value,
                _make_ordinal(user_entry.picross_count),
                strings.emoji_confirm
            )
            await self.view.fold_embed(interaction=interaction, embed=embed)

            # Send confirmation message in secret submission channel
            await self.submission_channel.send(content=strings.random("submission_verify_confirmation_responses").format(
                award_value,
                self.submission_author.mention,
                strings.emoji_confirm
            ))

        def get_award_data(self) -> dict:
            for entry in config.PICROSS_AWARDS:
                if entry["response_index"] == self.award_index:
                    return entry

    class SVerifyView(ui.View):
        def __init__(self, *, submission_author: User, submission_channel: TextChannel):
            super().__init__(timeout=0)

            for entry in config.PICROSS_AWARDS:
                self.add_item(SCommands.SVerifyButton(
                    award_index=entry["response_index"],
                    submission_author=submission_author,
                    submission_channel=submission_channel))
            self.add_item(SCommands.SVerifyRejectButton(
                submission_author=submission_author,
                submission_channel=submission_channel))

        async def fold_embed(self, interaction: Interaction, embed: Embed):
            # Clear verification message of buttons and images
            self.clear_items()
            embed.set_image(url=None)
            await interaction.message.edit(content=interaction.message.content, embed=embed, view=self)
            await interaction.response.defer()

    # Init

    def __init__(self, bot: Bot):
        super().__init__()

        self.bot: Bot = bot
        """
        Main bot instance.
        """

    # Default user commands

    @commands.command(name=strings.get("command_name_balance_get"))
    async def cmd_balance_get(self, ctx: Context, user_query: str = None) -> None:
        """
        Get your current balance, or another user by ID.
        :param ctx:
        :param user_query: Discord user ID, mention, or name to get balance for.
        """
        msg: str
        try:
            if not user_query:
                user_query = ctx.author.id
            user: User = await UserConverter().convert(
                ctx=ctx,
                argument=str(user_query).strip())
            response: SCommands.SResponse = self._do_balance_get(author=ctx.author, user=user)
            emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_shop"))
            msg = f"{emoji}\t{response.msg}"
        except BadArgument:
            msg = strings.get("commands_error_user")
        if msg:
            await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_balance_add"))
    async def cmd_balance_set(self, ctx: Context, user_query: str, value: int) -> None:
        """
        Take an amount from your balance to give to another user.
        :param ctx:
        :param user_query: Discord user ID, mention, or name to set balance for.
        :param value: Value to be added to balance.
        """
        msg: str
        try:
            user: User = await UserConverter().convert(
                ctx=ctx,
                argument=str(user_query).strip())
            if user.bot:
                raise BadArgument()
            response: SCommands.SResponse = self._do_balance_set(
                guild_id=ctx.guild.id,
                user_from=ctx.author,
                user_to=user,
                value=value)
            emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_shop"))
            msg = f"{emoji}\t{response.msg}"
        except BadArgument:
            msg = strings.get("commands_error_user")
        if msg:
            await ctx.reply(content=msg)

    # Admin commands

    @commands.command(name=strings.get("command_name_award"))
    @commands.check(requires_admin)
    async def cmd_award(self, ctx: Context, user_query: str, value: int) -> None:
        """
        Give an amount to another user's balance.

        Negative values will be deducted from their balance.
        :param ctx:
        :param user_query: Discord user ID, mention, or name to set balance for.
        :param value: Value to be added to balance.
        """
        msg: str
        try:
            user: User = await UserConverter().convert(
                ctx=ctx,
                argument=str(user_query).strip())
            if user.bot:
                raise BadArgument()
            response: SCommands.SResponse = self._do_award(
                guild_id=ctx.guild.id,
                user=user,
                value=value)
            emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_shop"))
            msg = f"{emoji}\t{response.msg}"
        except BadArgument:
            msg = strings.get("commands_error_user")
        if msg:
            await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_earnings"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_earnings(self, ctx: Context, value: Union[int, str] = None) -> None:
        """
        Get or set the total earnings for this guild, or a user if provided.

        Omitting value prints the current amount with no change to its value.
        :param ctx:
        :param value: Optional value; either user query, or balance change to apply to the guild earnings.
        """
        msg: str
        emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_shop"))
        guild_entry: db.DBGuild = db.get_guild(guild_id=ctx.guild.id)
        if value is None:
            # Omitting value will get current earnings
            msg = strings.get("commands_response_earnings_get").format(
                guild_entry.earnings,
                emoji
            )
        elif isinstance(value, str) or int(value) > 9999999:
            try:
                # Value will be read as a user query
                user: User = await UserConverter().convert(
                    ctx=ctx,
                    argument=str(value).strip())
                user_entry: db.DBUser = db.get_user(user_id=user.id)
                msg = strings.get("commands_response_earnings_user").format(
                    user.mention,
                    user_entry.earnings,
                    user_entry.balance,
                    emoji
                )
            except BadArgument:
                msg = strings.get("commands_error_user")
        else:
            # Including value will change current earnings
            earnings_previous: int = guild_entry.earnings
            earnings_difference: int = value - earnings_previous
            guild_entry.earnings = value
            db.update_guild(entry=guild_entry)
            msg = strings.get("commands_response_earnings_set").format(
                guild_entry.earnings,
                f"+{earnings_difference}" if earnings_difference >= 0 else earnings_difference,
                earnings_previous,
                emoji
            )
        if msg:
            await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_submissions_get"))
    @commands.check(requires_admin)
    async def cmd_submissions_get(self, ctx: Context, user_query: str = None) -> None:
        """
        Get your current contest submission count, or another user by ID.
        :param ctx:
        :param user_query: Discord user ID, mention, or name to get Picross wins for.
        """
        msg: str
        try:
            if not user_query:
                user_query = ctx.author.id
            user: User = await UserConverter().convert(
                ctx=ctx,
                argument=str(user_query).strip())
            if user.bot:
                raise BadArgument()
            user_entry: db.DBUser = db.get_user(user_id=user.id)
            if any(user_entry.submitted_channels):
                msg = strings.get("commands_response_submissions_get").format(
                    user.mention,
                    len(user_entry.submitted_channels),
                    " ".join([self.bot.get_channel(channel).mention for channel in user_entry.submitted_channels]),
                    strings.emoji_memo
                )
            else:
                msg = strings.get("commands_response_submissions_get_none").format(
                    user.mention
                )
        except BadArgument:
            msg = strings.get("commands_error_user")
        if msg:
            await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_picross_get"))
    @commands.check(requires_admin)
    async def cmd_picross_get(self, ctx: Context, user_query: str = None) -> None:
        """
        Get your current Picross puzzle count, or another user by ID.
        :param ctx:
        :param user_query: Discord user ID, mention, or name to get Picross wins for.
        """
        msg: str
        try:
            if not user_query:
                user_query = ctx.author.id
            user: User = await UserConverter().convert(
                ctx=ctx,
                argument=str(user_query).strip())
            if user.bot:
                raise BadArgument()
            user_entry: db.DBUser = db.get_user(user_id=user.id)
            msg = strings.get("commands_response_picross_get").format(
                user.mention,
                user_entry.picross_count,
                strings.emoji_memo
            )
        except BadArgument:
            msg = strings.get("commands_error_user")
        if msg:
            await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_forget_submissions"))
    @commands.check(requires_admin)
    async def cmd_forget_submissions(self, ctx: Context, user_query: str) -> None:
        """
        Forgets all user submissions, re-allowing awards in all channels.
        :param ctx:
        :param user_query: Discord user ID, mention, or name to forget submissions from.
        """
        msg: str
        try:
            user: User = await UserConverter().convert(
                ctx=ctx,
                argument=str(user_query).strip())
            user_entry: db.DBUser = db.get_user(user_id=user.id)

            # Send confirmation message
            emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_shop"))
            msg = strings.get("commands_response_forget_submissions").format(
                user.mention,
                len(user_entry.submitted_channels),
                emoji
            )

            # Forget submitted channels by clearing list in record
            user_entry.submitted_channels.clear()
            db.update_user(entry=user_entry)
        except BadArgument:
            msg = strings.get("commands_error_user")
        if msg:
            await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_enabled"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_enabled(self, ctx: Context) -> None:
        msg = "\n".join([
            strings.get("commands_response_enable_submission").format(strings.on_off(config.SUBMISSION_ENABLED))
        ])
        await ctx.reply(content=strings.get("commands_response_enabled").format(msg))

    @commands.command(name=strings.get("command_name_enable_submission"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_enable_submission(self, ctx: Context, is_enabled: bool = None) -> None:
        if is_enabled is not None:
            config.SUBMISSION_ENABLED = is_enabled
            _log_admin(msg_key="log_admin_enable_submission", user=ctx.author, value=strings.on_off(is_enabled))
        await ctx.reply(content=strings.get("commands_response_enable_submission").format(
            strings.on_off(config.SUBMISSION_ENABLED)))

    @commands.command(name=strings.get("command_name_sync"), hidden=True)
    @commands.check(requires_admin)
    async def cmd_sync(self, ctx: Context) -> None:
        _log_admin(msg_key="log_admin_sync", user=ctx.author)
        await self.bot.sync_guild(ctx.guild)
        await ctx.reply(content=strings.get("commands_response_sync"))

    @commands.command(name=strings.get("command_name_reload"), aliases=[config.COMMAND_PREFIX], hidden=True)
    @commands.check(requires_admin)
    async def cmd_reload(self, ctx: Context) -> None:
        """
        Reloads the commands extension, reapplying code changes and reloading the strings data file.
        """
        _log_admin(msg_key="log_admin_reload", user=ctx.author)
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
        await ctx.reply(
            content=strings.get("commands_response_test_string").format(string, msg)
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
        Updates the persistent role-button shop message.
        """
        msg: str = await self._do_update_shop(ctx=ctx)
        await ctx.reply(content=msg)

    @commands.command(name=strings.get("command_name_send_logs"), aliases=["log"])
    @commands.check(requires_admin)
    async def cmd_send_logs(self, ctx: Context) -> None:
        """
        Send a message with all available log files for this session.
        """
        fps: List[str] = [
            os.path.join(config.LOG_DIR, file)
            for file in os.listdir(config.LOG_DIR)
        ]
        files: List[File] = []
        for fp in fps:
            with open(file=fp, mode="r", encoding="utf8") as file:
                s: StringIO = StringIO()
                s.write(file.read())
                s.seek(0)
                files.append(File(s, filename=os.path.basename(fp)))

        hours: float = float(datetime.now().astimezone().strftime("%z")) / 100
        msg: str = strings.get("commands_response_logs" if files else "commands_response_logs_none").format(
            self.bot.start_time.strftime(strings.get("datetime_format_uptime")),
            f"+{hours}" if hours > 0 else hours)
        await ctx.reply(content=msg, files=files)

    @commands.command(name=strings.get("command_name_send_config"), aliases=["cfg"])
    @commands.check(requires_admin)
    async def cmd_send_config(self, ctx: Context) -> None:
        """
        Send a message with the contents of the config file.
        """
        config_file: File = None
        with open(file=config.PATH_CONFIG, mode="r", encoding="utf8") as file:
            js: dict = json.load(file)
            js["discord"] = "*" * len(js["discord"])
            s: StringIO = StringIO()
            s.write(json.dumps(js, indent=2, sort_keys=False))
            s.seek(0)
            config_file = File(s, filename=os.path.basename(config.PATH_CONFIG))
        msg: str = strings.get("commands_response_config").format(
            self.bot.start_time.strftime(strings.get("datetime_format_uptime")))
        await ctx.reply(content=msg, file=config_file)

    @commands.command(name=strings.get("command_name_update_avatar"))
    @commands.check(requires_admin)
    async def cmd_update_avatar(self, ctx: Context) -> None:
        """
        Updates bot client display picture.
        """
        _log_admin(msg_key="log_admin_avatar", user=ctx.author)

        msg: str = None
        attachment: Attachment = None
        original_avatar: File = None
        size_denom: int = 1000 * 1000
        size_max: int = 8

        # Fetch avatar from attachments
        if any(ctx.message.attachments):
            images: list = [a for a in ctx.message.attachments if re.match(r"image/(png|jpe?g)", a.content_type)]
            if any(images):
                images_usable: list = [a for a in images if a.size < size_denom * size_max]
                if not any(images_usable):
                    msg = strings.get("error_avatar_size").format(size_max)
                else:
                    attachment = images_usable[0]
        if not attachment:
            if not msg:
                msg = strings.get("error_avatar_not_found")
        else:
            original_avatar = await self.bot.user.display_avatar.to_file()
            attachment_bytes: bytes = await attachment.read()
            await self.bot.user.edit(avatar=attachment_bytes)
            await ctx.message.add_reaction(strings.emoji_confirm)
            msg = strings.get("commands_response_update_avatar").format(attachment.filename)

        await ctx.reply(content=msg, file=original_avatar)

    @commands.command(name=strings.get("command_name_update_username"))
    @commands.check(requires_admin)
    async def cmd_update_username(self, ctx: Context, username: str) -> None:
        """
        Updates bot client username.
        """
        _log_admin(msg_key="log_admin_username", user=ctx.author, value=username)

        msg: str = None
        try:
            original_username: str = self.bot.user.global_name or str(self.bot.user)
            await self.bot.user.edit(username=username)
            await ctx.message.add_reaction(strings.emoji_confirm)
            msg = strings.get("commands_response_update_username").format(original_username)
        except HTTPException as e:
            await ctx.message.add_reaction(strings.emoji_cancel)
            msg = strings.get("error_username_invalid").format(
                username,
                e.status,
                e.code,
                e.text or strings.get("error_no_info")
            )
        finally:
            if msg:
                await ctx.reply(content=msg)

    # Command implementations

    async def do_award_command(self, interaction: Interaction, message: Message):
        """
        Method handling Award context command behaviours.
        """
        msg_rejected: str = None
        msg_verified: str = None

        # Do staff verification on user messages in submission channels
        if not config.SUBMISSION_ENABLED:
            # Reject if submissions are disabled in config
            msg_rejected = strings.get("submission_disabled")
        elif message.channel.id not in _get_submission_data().keys():
            # Reject if award not given in submission channel
            msg_rejected = strings.get("submission_bad_channel").format(
                config.COMMAND_PREFIX,
                strings.get("command_name_award"))
        elif message.author.bot:
            # Reject if message author is bot
            msg_rejected = strings.get("submission_no_award")
        else:
            user_entry: db.DBUser = db.get_user(user_id=message.author.id)
            if message.channel.id in user_entry.submitted_channels:
                # Reject if user has already been awarded in this channel
                msg_rejected = strings.get("submission_duplicate").format(
                    message.author.mention)
            else:
                msg_verified = self._do_verification(message=message, user=interaction.user)
                if not msg_verified:
                    # Reject if failed to verify
                    msg_rejected = strings.get("submission_no_award")
                else:
                    # Award user for their first submission in this channel
                    emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_submissions"))
                    await interaction.response.send_message(content=f"{emoji} {message.author.mention} {msg_verified}")
                    await message.add_reaction(strings.emoji_confirm)
        if msg_rejected:
            # Send message to staff if rejected
            await interaction.response.send_message(content=msg_rejected, ephemeral=True)

    def _do_balance_get(self, author: User, user: User) -> SResponse:
        """
        Gets a user's balance.
        :param author: User checking balance.
        :param user: User to check.
        """
        user_entry: db.DBUser = db.get_user(user_id=user.id)
        msg_balance_key: str = "balance_responses_other" if author.id != user.id \
            else "balance_responses_none" if user_entry.balance < 1 \
            else "balance_responses_one" if user_entry.balance == 1 \
            else "balance_responses_many"
        msg: str = strings.random(msg_balance_key).format(user_entry.balance, user.mention)
        return SCommands.SResponse(msg=msg, value=user_entry.balance)

    def _do_balance_set(self, guild_id: int, user_from: User, user_to: User, value: int) -> SResponse:
        """
        Sets balance for a user.
        :param user_from: User donating balance.
        :param user_to: User receiving donation.
        :param value: Value to be added to user's balance.
        """
        guild_entry: db.DBGuild = db.get_guild(guild_id=guild_id)
        user_from_entry: db.DBUser = db.get_user(user_id=user_from.id)
        user_to_entry: db.DBUser = db.get_user(user_id=user_to.id)
        balance_donated: int = min(user_from_entry.balance, value)
        is_negative: bool = balance_donated < 1

        if user_from.id == user_to.id or value < 1:
            raise BadArgument()
        elif is_negative:
            value = 0
        else:
            # Add balance to target user
            _add_balance(guild_entry=guild_entry, user_entry=user_to_entry, value=balance_donated)
            # Deduct balance from self user
            _add_balance(guild_entry=guild_entry, user_entry=user_from_entry, value=-balance_donated)

        msg_balance_key: str = "balance_responses_too_low" if is_negative else "balance_responses_donated"
        msg: str = strings.random(msg_balance_key).format(
            balance_donated,
            user_from_entry.balance,
            user_to.mention,
            user_to_entry.balance)
        return SCommands.SResponse(msg=msg, value=value)

    def _do_award(self, guild_id: int, user: User, value: int) -> SResponse:
        """
        Adds a value to a user's balance.
        :param user: User receiving donation.
        :param value: Value to be added to user's balance.
        """
        guild_entry: db.DBGuild = db.get_guild(guild_id=guild_id)
        user_entry: db.DBUser = db.get_user(user_id=user.id)

        # Add to user's balance
        _add_balance(guild_entry=guild_entry, user_entry=user_entry, value=value)

        msg: str = strings.random("award_responses").format(value, user.mention)
        return SCommands.SResponse(msg=msg, value=value)

    async def _do_update_shop(self, ctx: Context) -> str:
        # Get roles and text for shop info
        guild_entry: db.DBGuild = db.get_guild(guild_id=ctx.guild.id)
        emoji: Emoji = utils.get(self.bot.emojis, name=strings.get("emoji_shop"))
        msg_roles: str = "\n".join([strings.get("message_shop_role").format(
            utils.get(self.bot.emojis, name=strings.get(f"emoji_hat_{role_data.get('name')}")),
            ctx.guild.get_role(role_data.get("id")).mention,
            role_data.get("cost")
        ) for role_data in config.SHOP_ROLE_LIST])
        msg: str
        shop_title: str = strings.get("message_shop_title").format(strings.emoji_shop)
        shop_body: str = strings.get("message_shop_body").format(msg_roles, emoji)

        # Create embed with shop info and button view
        embed: Embed = Embed(
            colour=ctx.guild.get_member(self.bot.user.id).colour,
            title=shop_title,
            description=shop_body)
        embed.set_thumbnail(url=emoji.url)
        view: View = SCommands.SShopView(guild=ctx.guild, bot=self.bot)
        channel: TextChannel = self.bot.get_channel(config.CHANNEL_SHOP)
        message: Message

        # Send or edit shop message
        if guild_entry.shop_message_id:
            message = await channel.get_partial_message(guild_entry.shop_message_id).edit(content=None, embed=embed, view=view)
            msg = strings.get("commands_response_edit_success").format(
                message.channel.mention,
                message.jump_url)
        else:
            message = await channel.send(content=None, embed=embed, view=view)
            msg = strings.get("commands_response_send_success").format(
                channel.mention,
                message.jump_url)

            # Update guild entry with shop message ID
            guild_entry.shop_message_id = message.id
            db.update_guild(entry=guild_entry)

        return msg

    # Event implementations

    async def _do_secret_submission(self, message: Message, verification_channel_id: int) -> Optional[str]:
        msg: str = None
        matches: Optional[re.Match[str]] = re.match(pattern=r"https?\S+", string=message.content)
        urls: List[str] = [i.proxy_url for i in message.attachments] \
                + [i.image.proxy_url for i in message.embeds if i.image and i.image.proxy_url] \
                + ([s for s in matches.groups()] if matches else [])

        # Send all messages in secret submission channels for verification, except admin messages without attachments
        for url in urls:
            # Send parsed copy in verification channel for each attachment
            embed: Embed = Embed(
                title=strings.get("submission_verify_title").format(
                    message.author.global_name or message.author,
                    message.channel.name
                ),
                description=message.content,
                colour=Colour.blurple(),
                url=url
            )
            embed.set_image(url=url)
            await self.bot.get_channel(verification_channel_id).send(
                content=msg,
                embed=embed,
                view=SCommands.SVerifyView(submission_author=message.author, submission_channel=message.channel))
        if urls or not check_roles(user=message.author, role_ids=[config.ROLE_ADMIN, config.ROLE_HELPER]):
            # Send receipt in submission channel
            msg = strings.get("submission_verify_response").format(
                message.author.mention,
                strings.emoji_memo
            )
            # Delete original message after sending
            await message.delete()

        return msg

    def _do_verification(self, message: Message, user: User) -> Optional[str]:
        """
        Staff reactions to posts with attachments in the submissions channel will add to the author's balance.
        :param message: Interaction message instance.
        :param user: User verifying the message.
        """
        guild_entry: db.DBGuild = db.get_guild(guild_id=message.guild.id)
        user_entry: db.DBUser = db.get_user(user_id=user.id)
        if message.channel.id not in user_entry.submitted_channels:
            submission_data: Dict[int, Tuple] = _get_submission_data()
            balance_earned: int
            msg_key: str

            # Update user balance
            balance_earned, msg_key = submission_data.get(message.channel.id, (0, None))
            if balance_earned < 1:
                return None
            _add_balance(guild_entry=guild_entry, user_entry=user_entry, value=balance_earned)

            # Update user submissions record
            user_entry.submitted_channels.append(message.channel.id)
            db.update_user(entry=user_entry)

            msg: str = strings.random(msg_key).format(balance_earned)
            return msg

    # Event listeners

    async def on_message(self, message: Message) -> None:
        msg: str = None

        # Ignore bot messages
        if message.author.bot:
            return

        # Handle secret submissions in submission channels
        submission_data: Dict[int, int] = _get_secret_submission_data()
        verify_channel_id: Optional[int] = submission_data.get(message.channel.id, None)
        if verify_channel_id:
            msg = await self._do_secret_submission(message=message, verification_channel_id=verify_channel_id)

        if msg:
            await message.channel.send(content=msg)

    async def on_command_error(self, ctx: Context, error: Exception) -> None:
        msg: str = None
        if ctx.command is None:
            msg = strings.get("error_command_not_found")
        else:
            # Makes perfect sense
            cmd: str = ctx.command.name
            cmd_str: List[str] = [s for s in strings.get("command_list") if strings.get(s) == cmd]
            cmd_internal_name: str = cmd_str[0].split("_", 2)[-1] if any(cmd_str) and "_" in cmd_str[0] else cmd_str
            if isinstance(error, CheckFailureQuietly):
                return
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


# Command utils


def _log_admin(msg_key: str, user: User, value: Any = None):
    msg: str = strings.get(msg_key).format(
        user.global_name or user,
        user.id,
        value)
    print(msg)
    logger: logging.Logger = logging.getLogger("discord")
    logger.log(level=logging.DEBUG, msg=msg)

def _add_balance(guild_entry: db.DBGuild, user_entry: db.DBUser, value: int) -> int:
    user_entry.balance += value
    if value > 0:
        user_entry.earnings += value
        _add_earnings(guild_entry=guild_entry, value=value)
    db.update_user(entry=user_entry)
    return user_entry.balance

def _add_earnings(guild_entry: db.DBGuild, value: int) -> int:
    if value > 0:
        guild_entry.earnings += value
        db.update_guild(entry=guild_entry)
    return guild_entry.earnings

def _get_secret_submission_data():
    return {
        config.CHANNEL_SUBMIT_PICROSS: config.CHANNEL_VERIFY_PICROSS
    }

def _get_submission_data() -> Dict[int, Tuple]:
    return {
        config.CHANNEL_SUBMIT_ART: (config.SUBMISSION_VALUE_ART, "submission_responses_art"),
        config.CHANNEL_SUBMIT_MODS: (config.SUBMISSION_VALUE_MODS, "submission_responses_mods"),
        config.CHANNEL_SUBMIT_WRITING: (config.SUBMISSION_VALUE_WRITING, "submission_responses_writing"),
        config.CHANNEL_SUBMIT_DECOR: (config.SUBMISSION_VALUE_DECOR, "submission_responses_decor"),
        config.CHANNEL_SUBMIT_HATS: (config.SUBMISSION_VALUE_HATS, "submission_responses_hats"),
    }
def _make_ordinal(n):
    """
    Florian Brucker - https://stackoverflow.com/a/50992575

    Convert an integer into its ordinal representation::

        make_ordinal(0)   => '0th'
        make_ordinal(3)   => '3rd'
        make_ordinal(122) => '122nd'
        make_ordinal(213) => '213th'
    """

    n = int(n)
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    return str(n) + suffix

# Discord.py boilerplate


async def setup(bot: Bot):
    # Add cog
    cog: SCommands = SCommands(bot=bot)
    await bot.add_cog(cog)

    # Add event listeners
    bot.add_listener(cog.on_message, name="on_message")
    bot.add_listener(cog.on_command_error, name="on_command_error")

    # Load data
    bot.reload_strings()
    reload(strings)
    reload(utils)
