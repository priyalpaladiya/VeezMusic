# Copyright (C) 2021 VeezMusicProject

import traceback
import asyncio
from asyncio import QueueEmpty
from config import que
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, Chat, CallbackQuery

from cache.admins import admins
from helpers.channelmusic import get_chat_id
from helpers.decorators import authorized_users_only, errors
from helpers.filters import command, other_filters
from callsmusic import callsmusic
from callsmusic import groupcall
from callsmusic.queues import queues
from config import LOG_CHANNEL, OWNER_ID, BOT_USERNAME
from helpers.database import db, dcmdb, Database
from helpers.dbtools import handle_user_status, delcmd_is_on, delcmd_on, delcmd_off


@Client.on_message()
async def _(bot: Client, cmd: Message):
    await handle_user_status(bot, cmd)

# Back Button
BACK_BUTTON = InlineKeyboardMarkup([[InlineKeyboardButton("🏡 BACK", callback_data="cbback")]])

@Client.on_message(filters.text & ~filters.private)
async def delcmd(_, message: Message):
    if await delcmd_is_on(message.chat.id) and message.text.startswith("/") or message.text.startswith("!"):
        await message.delete()
    await message.continue_propagation()


@Client.on_message(filters.command("reload"))
async def update_admin(client, message):
    global admins
    new_admins = []
    new_ads = await client.get_chat_members(message.chat.id, filter="administrators")
    for u in new_ads:
        new_admins.append(u.user.id)
    admins[message.chat.id] = new_admins
    await message.reply_text("✅ Bot **reloaded correctly !**\n✅ **Admin list** has been **updated !**")


# Control Menu Of Player
@Client.on_message(command(["control", f"control@{BOT_USERNAME}", "p"]))
@errors
@authorized_users_only
async def controlset(_, message: Message):
    await message.reply_text(
        "**💡 music player control menu opened !**",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⏸ pause music", callback_data="cbpause"
                    ),
                    InlineKeyboardButton(
                        "▶️ resume music", callback_data="cbresume"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⏩ skip music", callback_data="cbskip"
                    ),
                    InlineKeyboardButton(
                        "⏹ end music", callback_data="cbend"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔇 mute player", callback_data="cbmute"
                    ),
                    InlineKeyboardButton(
                        "🔊 unmute player", callback_data="cbunmute"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🗑 del cmd", callback_data="cbdelcmds"
                    )
                ]
            ]
        )
    )


@Client.on_message(command("pause") & other_filters)
@errors
@authorized_users_only
async def pause(_, message: Message):
    chat_id = get_chat_id(message.chat)
    if (chat_id not in callsmusic.pytgcalls.active_calls) or (
        callsmusic.pytgcalls.active_calls[chat_id] == "paused"
    ):
        await message.reply_text("❗ nothing in streaming!")
    else:
        callsmusic.pytgcalls.pause_stream(chat_id)
        await message.reply_text("▶️ music paused!")


@Client.on_message(command("resume") & other_filters)
@errors
@authorized_users_only
async def resume(_, message: Message):
    chat_id = get_chat_id(message.chat)
    if (chat_id not in callsmusic.pytgcalls.active_calls) or (
        callsmusic.pytgcalls.active_calls[chat_id] == "playing"
    ):
        await message.reply_text("❗ nothing is paused!")
    else:
        callsmusic.pytgcalls.resume_stream(chat_id)
        await message.reply_text("⏸ music resumed!")


@Client.on_message(command("end") & other_filters)
@errors
@authorized_users_only
async def stop(_, message: Message):
    chat_id = get_chat_id(message.chat)
    if chat_id not in callsmusic.pytgcalls.active_calls:
        await message.reply_text("❗ nothing in streaming!")
    else:
        try:
            queues.clear(chat_id)
        except QueueEmpty:
            pass

        callsmusic.pytgcalls.leave_group_call(chat_id)
        await message.reply_text("⏹ streaming ended!")


@Client.on_message(command("skip") & other_filters)
@errors
@authorized_users_only
async def skip(_, message: Message):
    global que
    chat_id = get_chat_id(message.chat)
    if chat_id not in callsmusic.pytgcalls.active_calls:
        await message.reply_text("❗ nothing in streaming!")
    else:
        queues.task_done(chat_id)

        if queues.is_empty(chat_id):
            callsmusic.pytgcalls.leave_group_call(chat_id)
        else:
            callsmusic.pytgcalls.change_stream(
                chat_id, queues.get(chat_id)["file"]
            )

    qeue = que.get(chat_id)
    if qeue:
        skip = qeue.pop(0)
    if not qeue:
        return
    await message.reply_text(f"⫸ skipped : **{skip[0]}**\n⫸ now playing : **{qeue[0][0]}**")


@Client.on_message(filters.command("auth"))
@authorized_users_only
async def authenticate(client, message):
    global admins
    if not message.reply_to_message:
        await message.reply("❗ reply to message to authorize user!")
        return
    if message.reply_to_message.from_user.id not in admins[message.chat.id]:
        new_admins = admins[message.chat.id]
        new_admins.append(message.reply_to_message.from_user.id)
        admins[message.chat.id] = new_admins
        await message.reply("🟢 user authorized.\n\nfrom now on, that's user can use the admin commands.")
    else:
        await message.reply("✅ user already authorized!")


@Client.on_message(filters.command("deauth"))
@authorized_users_only
async def deautenticate(client, message):
    global admins
    if not message.reply_to_message:
        await message.reply("❗ reply to message to deauthorize user!")
        return
    if message.reply_to_message.from_user.id in admins[message.chat.id]:
        new_admins = admins[message.chat.id]
        new_admins.remove(message.reply_to_message.from_user.id)
        admins[message.chat.id] = new_admins
        await message.reply("🔴 user deauthorized.\n\nfrom now that's user can't use the admin commands.")
    else:
        await message.reply("✅ user already deauthorized!")


# this is a anti cmd feature
@Client.on_message(filters.command(["delcmd", f"delcmd@{BOT_USERNAME}"]) & ~filters.private)
@authorized_users_only
async def delcmdc(_, message: Message):
    if len(message.command) != 2:
        await message.reply_text("read the /help message to know how to use this command")
        return
    status = message.text.split(None, 1)[1].strip()
    status = status.lower()
    chat_id = message.chat.id
    if status == "on":
        if await delcmd_is_on(message.chat.id):
            await message.reply_text("✅ already activated")
            return
        else:
            await delcmd_on(chat_id)
            await message.reply_text(
                "🟢 activated successfully"
            )
    elif status == "off":
        await delcmd_off(chat_id)
        await message.reply_text("🔴 disabled successfully")
    else:
        await message.reply_text(
            "read the /help message to know how to use this command"
        )


@Client.on_message(command(["silent", f"silent@{BOT_USERNAME}", "m"]))
@errors
@authorized_users_only
async def silent(_, message: Message):
    result = groupcall.mute(message.chat.id)

    if result == 0:
        await message.reply_text("🔇 assistant muted")
    elif result == 1:
        await message.reply_text("✅ assistant already muted")
    elif result == 2:
        await message.reply_text("❗️ not connected to voice chat")


@Client.on_message(command(["unsilent", f"unsilent@{BOT_USERNAME}", "um"]))
@errors
@authorized_users_only
async def unsilent(_, message: Message):
    result = groupcall.unmute(message.chat.id)

    if result == 0:
        await message.reply_text("🔊 assistant unmuted")
    elif result == 1:
        await message.reply_text("✅ assistant already unmuted")
    elif result == 2:
        await message.reply_text("❗️ not connected to voice chat")


# music player callbacks (control by buttons feature)

@Client.on_callback_query(filters.regex("cbpause"))
async def cbpause(_, query: CallbackQuery):
    if groupcall.pause(query.message.chat.id):
        await query.edit_message_text("⏸ music paused", reply_markup=BACK_BUTTON)
    else:
        await query.edit_message_text("❗️ nothing is playing", reply_markup=BACK_BUTTON)

@Client.on_callback_query(filters.regex("cbresume"))
async def cbresume(_, query: CallbackQuery):
    if groupcall.resume(query.message.chat.id):
        await query.edit_message_text("▶ music resumed", reply_markup=BACK_BUTTON)
    else:
        await query.edit_message_text("❗️ nothing is paused", reply_markup=BACK_BUTTON)

@Client.on_callback_query(filters.regex("cbend"))
async def cbend(_, query: CallbackQuery):
    if query.message.chat.id not in groupcall.active_chats:
        await query.edit_message_text("❗️ nothing is playing", reply_markup=BACK_BUTTON)
    else:
        try:
            queues.clear(query.message.chat.id)
        except QueueEmpty:
            pass

        await groupcall.stop(query.message.chat.id)
        await query.edit_message_text("✅ cleared the queue and left the voice chat!", reply_markup=BACK_BUTTON)

@Client.on_callback_query(filters.regex("cbskip"))
async def cbskip(_, query: CallbackQuery):
     if query.message.chat.id not in groupcall.active_chats:
        await query.edit_message_text("❗️ nothing is playing", reply_markup=BACK_BUTTON)
     else:
        queues.task_done(query.message.chat.id)
        
        if queues.is_empty(query.message.chat.id):
            await groupcall.stop(query.message.chat.id)
        else:
            await groupcall.set_stream(
                query.message.chat.id, queues.get(query.message.chat.id)["file"]
            )

        await query.edit_message_text("⏭ skipped to the next music", reply_markup=BACK_BUTTON)

@Client.on_callback_query(filters.regex("cbmute"))
async def cbmute(_, query: CallbackQuery):
    result = groupcall.mute(query.message.chat.id)

    if result == 0:
        await query.edit_message_text("🔇 assistant muted", reply_markup=BACK_BUTTON)
    elif result == 1:
        await query.edit_message_text("✅ assistant already muted", reply_markup=BACK_BUTTON)
    elif result == 2:
        await query.edit_message_text("❗️ not connected to voice chat", reply_markup=BACK_BUTTON)

@Client.on_callback_query(filters.regex("cbunmute"))
async def cbunmute(_, query: CallbackQuery):
    result = groupcall.unmute(query.message.chat.id)

    if result == 0:
        await query.edit_message_text("🔊 assistant unmuted", reply_markup=BACK_BUTTON)
    elif result == 1:
        await query.edit_message_text("✅ assistant already unmuted", reply_markup=BACK_BUTTON)
    elif result == 2:
        await query.edit_message_text("❗️ not connected to voice chat", reply_markup=BACK_BUTTON)

# (C) supun-maduraga for his project on call-music-plus 
