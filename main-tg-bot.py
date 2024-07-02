# main_tg_bot.py
import os
import time
import asyncio
import logging
import requests
import subprocess
from aiogram import Bot, Dispatcher
from aiogram.utils import exceptions as aiogram_exceptions
from telethon import TelegramClient, events
from telethon.errors.rpcerrorlist import FloodWaitError, MessageNotModifiedError
from telethon.tl.functions.messages import UpdatePinnedMessageRequest, EditMessageRequest, DeleteMessagesRequest
from config import *
from file_uploader import download_and_send_media, download_and_send_large_media, download_media_without_sending, handle_flood_wait, load_sent_files, send_message_with_retry
from shared import aiogram_bot, TEXT_MESSAGES, USER_MESSAGES, client, switch_api_key, logger, current_split_process, processes, LAST_MESSAGE_CONTENT


# Initialize aiogram bot
dp = Dispatcher(aiogram_bot)

def send_fallback_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message
    }
    response = requests.post(url, data=data)
    if response.status_code != 200:
        logger.error(f"Failed to send fallback message: {response.text}")

def run_script(args):
    process = subprocess.Popen(['python3', ONLYFANS_DL_SCRIPT] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = [], []
    for line in iter(process.stdout.readline, ''):
        logger.info(line.strip())
        stdout.append(line.strip())
    for line in iter(process.stderr.readline, ''):
        logger.error(line.strip())
        stderr.append(line.strip())
    process.stdout.close()
    process.stderr.close()
    process.wait()
    return '\n'.join(stdout), '\n'.join(stderr)

@client.on(events.NewMessage(pattern='/get$'))
async def get_command_usage(event):
    if event.sender_id == TELEGRAM_USER_ID:
        msg = await event.respond("Usage: /get <username or subscription number> <max_age (optional)>")
        TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/get (.+)'))
async def get_command(event):
    if event.sender_id != TELEGRAM_USER_ID:
        msg = await event.respond("Unauthorized access.")
        USER_MESSAGES.append(msg.id)
        logger.warning(f"Unauthorized access denied for {event.sender_id}.")
        return

    args = event.pattern_match.group(1).strip().split()
    target = args[0]
    max_age = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
    tag = f"#{target}"

    try:
        with open("subscriptions_list.txt", "r") as f:
            subscriptions = f.readlines()

        if target.isdigit():
            target_index = int(target) - 1
            if target_index < 0 or target_index >= len(subscriptions):
                raise IndexError
            username = subscriptions[target_index].strip()
            tag = f"#{username}"
        else:
            username = target
            tag = f"#{target}"

        if username not in [sub.strip() for sub in subscriptions]:
            msg = await event.respond(f"User {username} not found in the subscriptions list. {tag}")
            USER_MESSAGES.append(msg.id)
            return
    except (IndexError, FileNotFoundError):
        msg = await event.respond("Invalid subscription number or subscriptions list not found.")
        USER_MESSAGES.append(msg.id)
        return

    if not os.path.exists(username):
        os.makedirs(username)
        msg = await event.respond(f"User directory {username} not found. Starting a fresh download. {tag}")
        USER_MESSAGES.append(msg.id)

    try:
        pinned_message = await event.respond(f"Started downloading media for {username} {tag}")
        TEXT_MESSAGES.append(pinned_message.id)
        pinned_message_id = pinned_message.id
        await client(UpdatePinnedMessageRequest(
            peer=event.chat_id,
            id=pinned_message_id,
            silent=True
        ))

        await download_and_send_media(username, event.chat_id, tag, pinned_message_id, max_age, event, client)
    except FloodWaitError as e:
        wait_time = e.seconds
        await handle_flood_wait(event.chat_id, wait_time, client)
    except Exception as e:
        await event.respond(f"Unexpected error occurred: {str(e)}")

@client.on(events.NewMessage(pattern='/get_big$'))
async def get_big_command_usage(event):
    if event.sender_id == TELEGRAM_USER_ID:
        msg = await event.respond("Usage: /get_big <username or subscription number>")
        TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/get_big (.+)'))
async def get_big_command(event):
    if event.sender_id != TELEGRAM_USER_ID:
        msg = await event.respond("Unauthorized access.")
        USER_MESSAGES.append(msg.id)
        logger.warning(f"Unauthorized access denied for {event.sender_id}.")
        return

    args = event.pattern_match.group(1).strip().split()
    target = args[0]
    max_age = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
    tag = f"#{target}"

    try:
        with open("subscriptions_list.txt", "r") as f:
            subscriptions = f.readlines()

        if target.isdigit():
            target_index = int(target) - 1
            if target_index < 0 or target_index >= len(subscriptions):
                raise IndexError
            username = subscriptions[target_index].strip()
            tag = f"#{username}"
        else:
            username = target
            tag = f"#{target}"

        if username not in [sub.strip() for sub in subscriptions]:
            msg = await event.respond(f"User {username} not found in the subscriptions list. {tag}")
            USER_MESSAGES.append(msg.id)
            return
    except (IndexError, FileNotFoundError):
        msg = await event.respond("Invalid subscription number or subscriptions list not found.")
        USER_MESSAGES.append(msg.id)
        return

    if not os.path.exists(username):
        os.makedirs(username)
        msg = await event.respond(f"User directory {username} not found. Starting a fresh download. {tag}")
        USER_MESSAGES.append(msg.id)

    try:
        pinned_message = await event.respond(f"Started downloading large media for {username} {tag}")
        TEXT_MESSAGES.append(pinned_message.id)
        pinned_message_id = pinned_message.id
        await client(UpdatePinnedMessageRequest(
            peer=event.chat_id,
            id=pinned_message_id,
            silent=True
        ))

        await download_and_send_large_media(username, event.chat_id, tag, pinned_message_id, max_age, event, client)
    except FloodWaitError as e:
        wait_time = e.seconds
        await handle_flood_wait(event.chat_id, wait_time, client)
    except Exception as e:
        await event.respond(f"Unexpected error occurred: {str(e)}")

@client.on(events.NewMessage(pattern='/load$'))
async def load_command_usage(event):
    if event.sender_id == TELEGRAM_USER_ID:
        await send_message_with_retry(event.chat_id, "Usage: /load <username or subscription number> <max_age (optional)>")

@client.on(events.NewMessage(pattern='/load (.+)'))
async def load_command(event):
    if event.sender_id != TELEGRAM_USER_ID:
        await send_message_with_retry(event.chat_id, "Unauthorized access.")
        logger.warning(f"Unauthorized access denied for {event.sender_id}.")
        return

    args = event.pattern_match.group(1).strip().split()
    if not args:
        await send_message_with_retry(event.chat_id, "Usage: /load <username or subscription number> <max_age (optional)>")
        return

    target = args[0]
    max_age = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0
    tag = f"#{target}"

    try:
        with open("subscriptions_list.txt", "r") as f:
            subscriptions = f.readlines()

        if target.isdigit():
            target_index = int(target) - 1
            if target_index < 0 or target_index >= len(subscriptions):
                raise IndexError
            username = subscriptions[target_index].strip()
            tag = f"#{username}"
        else:
            username = target
            tag = f"#{target}"

        if username not in [sub.strip() for sub in subscriptions]:
            await send_message_with_retry(event.chat_id, f"User {username} not found in the subscriptions list. {tag}")
            return
    except (IndexError, FileNotFoundError):
        await send_message_with_retry(event.chat_id, "Invalid subscription number or subscriptions list not found.")
        return

    if not os.path.exists(username):
        os.makedirs(username)
        await send_message_with_retry(event.chat_id, f"User directory {username} not found. Starting a fresh download. {tag}")

    try:
        await send_message_with_retry(event.chat_id, f"Started downloading media to server for {username} {tag}")
        await download_media_without_sending(username, event.chat_id, tag, max_age)
    except aiogram_exceptions.RetryAfter as e:
        await asyncio.sleep(e.timeout)
        await download_media_without_sending(username, event.chat_id, tag, max_age)

@client.on(events.NewMessage(pattern='/check$'))
async def check_command(event):
    if event.sender_id != TELEGRAM_USER_ID:
        msg = await event.respond("Unauthorized access.")
        USER_MESSAGES.append(msg.id)
        logger.warning(f"Unauthorized access denied for {event.sender_id}.")
        return

    try:
        header = "**__profile (sent/total)__**\n"
        separator = "--------------------------\n"
        response = header + separator  # Adding the header and separator to the response

        with open("subscriptions_list.txt", "r") as f:
            subscriptions = f.readlines()

        for profile in subscriptions:
            profile = profile.strip()
            profile_dir = os.path.join('.', profile)
            if os.path.exists(profile_dir) and os.path.isdir(profile_dir):
                sent_files = load_sent_files(profile_dir)
                total_files = 0
                for root, _, files in os.walk(profile_dir):
                    for file in files:
                        if file != 'sent_files.txt' and file.lower().endswith(('jpg', 'jpeg', 'png', 'mp4', 'mp3', 'gif')):
                            total_files += 1
                response += f"`{profile}` ({len(sent_files)}/**{total_files}**)\n"

        if response.strip() == header + separator:
            msg = await event.respond("No downloaded profiles found.")
            USER_MESSAGES.append(msg.id)
        else:
            msg = await event.respond(response)
            TEXT_MESSAGES.append(msg.id)
    except Exception as e:
        logger.error(f"Error checking profiles: {str(e)}")
        msg = await event.respond("Error checking profiles.")
        USER_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/erase$'))
async def erase_command_usage(event):
    if event.sender_id == TELEGRAM_USER_ID:
        msg = await event.respond("Usage: /erase <username or subscription number>")
        TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/erase (.+)'))
async def erase_command(event):
    if event.sender_id != TELEGRAM_USER_ID:
        msg = await event.respond("Unauthorized access.")
        USER_MESSAGES.append(msg.id)
        logger.warning(f"Unauthorized access denied for {event.sender_id}.")
        return

    target = event.pattern_match.group(1).strip()

    try:
        with open("subscriptions_list.txt", "r") as f:
            subscriptions = f.readlines()

        if target.isdigit():
            target_index = int(target) - 1
            if target_index < 0 or target_index >= len(subscriptions):
                raise IndexError
            username = subscriptions[target_index].strip()
            tag = f"#{username}"
        else:
            username = target
            tag = f"#{target}"

        if username not in [sub.strip() for sub in subscriptions]:
            msg = await event.respond(f"User {username} not found in the subscriptions list. {tag}")
            USER_MESSAGES.append(msg.id)
            return
    except (IndexError, FileNotFoundError):
        msg = await event.respond("Invalid subscription number or subscriptions list not found.")
        USER_MESSAGES.append(msg.id)
        return

    message_ids_to_delete = []

    for msg_id in TEXT_MESSAGES + USER_MESSAGES:
        try:
            message = await client.get_messages(event.chat_id, ids=msg_id)
            if message and tag in message.message:
                message_ids_to_delete.append(msg_id)
        except:
            continue

    if message_ids_to_delete:
        try:
            await client.delete_messages(event.chat_id, message_ids_to_delete)
            msg = await event.respond(f"All messages and media with tag {tag} have been erased.")
            USER_MESSAGES.append(msg.id)
        except Exception as e:
            logger.error(f"Failed to delete messages: {str(e)}")
            msg = await event.respond("Failed to delete messages.")
            USER_MESSAGES.append(msg.id)
    else:
        msg = await event.respond(f"No messages or media with tag {tag} found.")
        USER_MESSAGES.append(msg.id)

    # delete user folder from server
    if os.path.exists(username):
        subprocess.call(['rm', '-rf', username])




@client.on(events.NewMessage(pattern='/del$'))
async def del_command_usage(event):
    if event.sender_id == TELEGRAM_USER_ID:
        msg = await event.respond("Usage: /del <username or subscription number>")
        TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/del (.+)'))
async def del_command(event):
    if event.sender_id != TELEGRAM_USER_ID:
        msg = await event.respond("Unauthorized access.")
        TEXT_MESSAGES.append(msg.id)
        logger.warning(f"Unauthorized access denied for {event.sender_id}.")
        return

    target = event.pattern_match.group(1).strip()
    tag = f"#{target}"

    try:
        with open("subscriptions_list.txt", "r") as f:
            subscriptions = f.readlines()

        if target.isdigit():
            target_index = int(target) - 1
            if target_index < 0 or target_index >= len(subscriptions):
                raise IndexError
            username = subscriptions[target_index].strip()
        else:
            username = target

        if username not in [sub.strip() for sub in subscriptions]:
            msg = await event.respond(f"User {username} not found in the subscriptions list. {tag}")
            TEXT_MESSAGES.append(msg.id)
            return
    except (IndexError, FileNotFoundError):
        msg = await event.respond("Invalid subscription number or subscriptions list not found.")
        TEXT_MESSAGES.append(msg.id)
        return

    # delete user folder from server
    if os.path.exists(username):
        subprocess.call(['rm', '-rf', username])
        msg = await event.respond(f"User directory {username} has been deleted. {tag}")
        TEXT_MESSAGES.append(msg.id)
    else:
        msg = await event.respond(f"User directory {username} not found. {tag}")
        TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/user_id$'))
async def user_id_command_usage(event):
    if event.sender_id == TELEGRAM_USER_ID:
        msg = await event.respond("Usage: /user_id <new_user_id>")
        TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/user_id (.+)'))
async def user_id_command(event):
    if event.sender_id == TELEGRAM_USER_ID:
        user_id = event.pattern_match.group(1).strip()
        try:
            update_config('USER_ID', user_id)
            msg = await event.respond(f"USER_ID updated to: {user_id}")
            TEXT_MESSAGES.append(msg.id)
        except ValueError as e:
            msg = await event.respond(str(e))
            TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/user_agent$'))
async def user_agent_command_usage(event):
    if event.sender_id == TELEGRAM_USER_ID:
        msg = await event.respond("Usage: /user_agent <new_user_agent>")
        TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/user_agent (.+)'))
async def user_agent_command(event):
    if event.sender_id == TELEGRAM_USER_ID:
        user_agent = event.pattern_match.group(1).strip()
        try:
            update_config('USER_AGENT', user_agent)
            msg = await event.respond(f"USER_AGENT updated to: {user_agent}")
            TEXT_MESSAGES.append(msg.id)
        except ValueError as e:
            msg = await event.respond(str(e))
            TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/x_bc$'))
async def x_bc_command_usage(event):
    if event.sender_id == TELEGRAM_USER_ID:
        msg = await event.respond("Usage: /x_bc <new_x_bc>")
        TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/x_bc (.+)'))
async def x_bc_command(event):
    if event.sender_id == TELEGRAM_USER_ID:
        x_bc = event.pattern_match.group(1).strip()
        try:
            update_config('X_BC', x_bc)
            msg = await event.respond(f"X_BC updated to: {x_bc}")
            TEXT_MESSAGES.append(msg.id)
        except ValueError as e:
            msg = await event.respond(str(e))
            TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/sess_cookie$'))
async def sess_cookie_command_usage(event):
    if event.sender_id == TELEGRAM_USER_ID:
        msg = await event.respond("Usage: /sess_cookie <new_sess_cookie>")
        TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage(pattern='/sess_cookie (.+)'))
async def sess_cookie_command(event):
    if event.sender_id == TELEGRAM_USER_ID:
        sess_cookie = event.pattern_match.group(1).strip()
        try:
            update_config('SESS_COOKIE', sess_cookie)
            msg = await event.respond(f"SESS_COOKIE updated to: {sess_cookie}")
            TEXT_MESSAGES.append(msg.id)
        except ValueError as e:
            msg = await event.respond(str(e))
            TEXT_MESSAGES.append(msg.id)

@client.on(events.NewMessage())
async def track_user_messages(event):
    if event.sender_id == TELEGRAM_USER_ID:
        if not event.message.media:  # Проверяем, что сообщение не содержит медиа
            USER_MESSAGES.append(event.id)
            TEXT_MESSAGES.append(event.id)  # Отслеживаем только текстовые сообщения
        else:
            USER_MESSAGES.append(event.id)  # Отслеживаем все сообщения для удаления по команде /clear

@client.on(events.NewMessage(pattern='/clear'))
async def clear_command(event):
    if event.sender_id == TELEGRAM_USER_ID:
        messages_to_delete = []

        # Добавляем идентификатор, чтобы удалить это сообщение
        messages_to_delete.append(event.id)

        # Удаляем только текстовые сообщения, отслеживаемые в TEXT_MESSAGES и USER_MESSAGES
        for msg_id in TEXT_MESSAGES + USER_MESSAGES:
            try:
                message = await client.get_messages(event.chat_id, ids=msg_id)
                if message and not message.media:  # Удаляем только текстовые сообщения
                    messages_to_delete.append(msg_id)
            except:
                continue

        # Удаляем отслеживаемые сообщения
        try:
            await client.delete_messages(event.chat_id, messages_to_delete)
        except FloodWaitError as e:
            await handle_flood_wait(event.chat_id, e.seconds, client)

        # Очищаем отслеживаемые ID сообщений
        TEXT_MESSAGES.clear()
        USER_MESSAGES.clear()
        global last_flood_wait_message_time
        last_flood_wait_message_time = None  # Сбрасываем таймер FloodWaitError


@client.on(events.NewMessage(pattern='/restart'))
async def restart_command(event):
    global current_split_process
    try:
        if event.sender_id == TELEGRAM_USER_ID:
            if current_split_process:
                current_split_process.terminate()
                current_split_process.wait()
                current_split_process = None
                await event.respond("Current process is stopped. Telegram bot is restarting.")
            else:
                await event.respond("No process is running. Telegram bot is restarting")
            # Restart the bot by restarting the script
            os.system("pkill -f main_tg_bot.py")  # Kills the script
            os.system("python3 main_tg_bot.py &")  # Restarts the script
    except FloodWaitError as e:
        wait_time = e.seconds
        await handle_flood_wait(event.chat_id, wait_time, client)

@client.on(events.NewMessage(pattern='/list'))
async def list_command(event):
    if event.sender_id != TELEGRAM_USER_ID:
        msg = await event.respond("Unauthorized access.")
        USER_MESSAGES.append(msg.id)
        logger.warning(f"Unauthorized access denied for {event.sender_id}.")
        return

    stdout, stderr = run_script(['--list'])
    if stderr:
        msg = await event.respond(f"Error: {stderr}")
        TEXT_MESSAGES.append(msg.id)
    else:
        try:
            with open("subscriptions_list.txt", "r") as f:
                subscriptions = f.readlines()
            if not subscriptions:
                msg = await event.respond("No active subscriptions found.")
                TEXT_MESSAGES.append(msg.id)
                return
            # print subscription list with numbers and markdown format
            markdown_subs = ''.join([f"{i+1}. `{sub.strip()}`\n" for i, sub in enumerate(subscriptions)])
            msg = await event.respond(markdown_subs, parse_mode='md')
            TEXT_MESSAGES.append(msg.id)
        except FileNotFoundError:
            msg = await event.respond("Error: subscriptions_list.txt not found.")
            TEXT_MESSAGES.append(msg.id)

async def setup_aiogram_bot_commands(dp: Dispatcher):
    commands = [
        {"command": "list", "description": "Show list of active subscriptions"},
        {"command": "get", "description": "Download media and send to this chat"},
        {"command": "get_big", "description": "Download and send large media files"},
        {"command": "load", "description": "Download media to server without sending"},
        {"command": "check", "description": "Check downloaded profiles and media count"},
        {"command": "erase", "description": "Erase chat messages with a specific hashtag"},
        {"command": "del", "description": "Delete profile folder from server"},
        {"command": "clear", "description": "Clear non-media messages in chat"},
        {"command": "restart", "description": "Stop current process and restart bot"},
        {"command": "user_id", "description": "Update USER_ID"},
        {"command": "user_agent", "description": "Update USER_AGENT"},
        {"command": "x_bc", "description": "Update X_BC"},
        {"command": "sess_cookie", "description": "Update SESS_COOKIE"}
    ]

    await dp.bot.set_my_commands(commands)

async def on_startup(dp):
    await setup_aiogram_bot_commands(dp)

def main():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(on_startup(dp))
    client.run_until_disconnected()

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
