#!/usr/bin/env python
import RPi.GPIO as GPIO  
import keybow
import time
import os
import subprocess
import pygame
import time
import logging
from telegram import Update
from telegram.ext import (ApplicationBuilder, ContextTypes, CommandHandler,
                          MessageHandler, PollHandler, filters)
import configparser

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

PLAY_KEY = 0
MID_KEY = 3
REC_KEY = 6

REC_COLOR = [227, 100, 136] # Red
PLAY_COLOR = [174, 244, 164] # Green
MID_COLOR = [121, 184, 209] # Blue

colors = {
    REC_KEY : REC_COLOR,
    MID_KEY : MID_COLOR,
    PLAY_KEY : PLAY_COLOR,
}

@keybow.on()
def handle_key(index, state):
    if state:
        if index == PLAY_KEY:
            try:
                p = subprocess.Popen(["mplayer", "voice.ogg"])
            except ValueError as ve:
                print(ve)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f'Message: {update.message}')
    print(update.message.voice)
    if update.message.voice is not None:
        logging.info(f'Voice from:{update.message.from_user} :: {update.message.voice.duration}s')

        file_id = update.message.voice.file_id
        new_file = await context.bot.get_file(file_id)
        await new_file.download_to_drive('voice.ogg')

        keybow.set_led(PLAY_KEY+3, *colors[PLAY_KEY])
        keybow.show()
        time.sleep(10)
        keybow.clear()
        keybow.show()
    else:
        logging.info(f'Message from:{update.message.from_user} :: {update.message.text}')
        keybow.set_led(MID_KEY+3, *colors[MID_KEY])
        keybow.show()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)
        time.sleep(10)
        keybow.clear()
        keybow.show()

async def message_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f'Message: {update.message}')

async def voice_echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f'Voice from:{update.message.from_user} :: {update.message.audio.duration}s')

if __name__ == '__main__':
    conf = configparser.ConfigParser()
    conf.read('tele.conf')

    application = ApplicationBuilder().token(conf['bot']['bot_key']).build()
    
    start_handler = CommandHandler('start', start)
    echo_handler = MessageHandler((filters.TEXT | filters.VOICE | filters.AUDIO) & (~filters.COMMAND), echo)
    log_handler = MessageHandler((~filters.COMMAND), message_log)

    application.add_handler(start_handler)
    application.add_handler(echo_handler)
    
    application.run_polling()
