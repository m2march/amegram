#!/usr/bin/env python
import RPi.GPIO as GPIO  
import keybow
import logging
import time
from telegram import Update
from telegram.ext import (ApplicationBuilder, ContextTypes, CommandHandler,
                          MessageHandler, PollHandler, filters)
import configparser
import sounddevice as sd
import pydub
from scipy.io import wavfile
import numpy as np
import asyncio
from pathlib import Path

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

sd.default.device = [0, 1]
recording_rate = 44000
recording_time = 15
target_user = 76053031 #"@M2March"

new_outgoing_message = asyncio.Event()

@keybow.on()
def handle_key(index, state):
    if state:
        if index == PLAY_KEY:
            logging.info('Playing sound')
            a = pydub.AudioSegment.from_file('voice.ogg')
            sd.play(a.get_array_of_samples())
            logging.info('Playback done')
        elif index == REC_KEY:
            logging.info('Recording sound')
            start_time = time.time()
            r = sd.rec(recording_time * recording_rate, 
                       samplerate=recording_rate,
                       channels=1, blocking=False)
            logging.info('Recording started')
            while time.time() - start_time < recording_time:
                passed_time = time.time() - start_time
                key_alpha = (np.cos(passed_time / (2 * np.pi)) + 1) / 2
                key_color = np.array(colors[REC_KEY]) * key_alpha
                key_color = [int(x) for x in key_color]
                keybow.set_led(REC_KEY+3, *key_color)
                keybow.show()
                time.sleep(0.1)
            logging.info('Recording ended')
            keybow.set_led(REC_KEY+3, *colors[REC_KEY])
            keybow.show()
            wavfile.write('rec.wav', recording_rate, r)
            a = pydub.AudioSegment.from_file('rec.wav')
            a.export('rec.ogg', format='ogg')
            logging.info('Recording done')
            new_outgoing_message.set()


async def send_voice_note(bot):
    while True:
        await new_outgoing_message.wait()
        new_outgoing_message.clear()
        logging.info(f'Sending voice message to: {target_user}')
        await bot.send_voice(target_user, Path('rec.ogg'))
        logging.info(f'Done sending voice message')


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

async def main():
    conf = configparser.ConfigParser()
    conf.read('tele.conf')

    keybow.set_led(REC_KEY+3, *colors[REC_KEY])
    keybow.show()

    application = ApplicationBuilder().token(conf['bot']['bot_key']).build()
    
    start_handler = CommandHandler('start', start)
    echo_handler = MessageHandler((filters.TEXT | filters.VOICE | filters.AUDIO) & (~filters.COMMAND), echo)
    log_handler = MessageHandler((~filters.COMMAND), message_log)

    application.add_handler(start_handler)
    application.add_handler(echo_handler)

    async with application:
        await application.start()
        await application.updater.start_polling()

        send_task = asyncio.create_task(send_voice_note(application.bot))

        await send_task

        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
