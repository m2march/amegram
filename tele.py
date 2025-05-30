#!/usr/bin/env python
import RPi.GPIO as GPIO  
import keybow
import logging
import time
from telegram import Update
from telegram.ext import (ApplicationBuilder, ContextTypes, CommandHandler,
                          MessageHandler, PollHandler, filters)
import configparser
import os
import sounddevice as sd
import pydub
from scipy.io import wavfile
import numpy as np
import asyncio
from pathlib import Path

logging.basicConfig(
    filename='amegram.log',
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
max_recording_time = 10 * 60
target_user = 76053031 #"@M2March"
amp_correction = 1#9
telegram_polling_interval = 0.5
volume_options = [10, 30, 50, 70, 90, 100]
current_volume_idx = 2

new_outgoing_message = asyncio.Event()
new_incoming_message = asyncio.Event()
recording_message = asyncio.Event()

@keybow.on()
def handle_key(index, state):
    if state:
        if index == PLAY_KEY:
            logging.info('Playing sound')
            sr, d = wavfile.read('voice.wav')
            sd.play(d, samplerate=sr, blocking=False)
            blinking_light(lambda t: t < d.shape[0] / sr,
                           PLAY_KEY, colors[PLAY_KEY], 2)
            logging.info('Playback done')
            new_incoming_message.clear()
        elif index == REC_KEY:
            if recording_message.is_set():
                logging.info('Finishing recording')
                recording_message.clear()
            else:
                logging.info('Recording sound')
                recording_message.set()
                time.sleep(0.0)
        elif index == MID_KEY:
            inc_volume()


def adjust_color_alpha(color_arr, alpha):
    return [int(x) for x in np.array(color_arr) * alpha]


def inc_volume():
    global current_volume_idx
    current_volume_idx = (current_volume_idx + 1) % len(volume_options)
    cur_vol = volume_options[current_volume_idx]
    os.system(f'amixer -D pulse set Master {str(cur_vol)}%')
    alpha = (cur_vol / 100) * .7 + .3
    keybow.set_led(MID_KEY+3, 
                   *adjust_color_alpha(colors[MID_KEY], alpha))
    keybow.show()

def blinking_light(cond_f, key, color_arr, freq=2, sleep_time=0.1):
    start_time = time.time()
    passed_time = time.time() - start_time
    while (cond_f(passed_time)):
        key_alpha = (np.cos(passed_time * freq * (2 * np.pi)) + 1) / 2
        key_color = adjust_color_alpha(color_arr, key_alpha)
        keybow.set_led(key+3, *key_color)
        keybow.show()
        time.sleep(sleep_time)
        passed_time = time.time() - start_time


async def incoming_light():
    while True:
        await new_incoming_message.wait()
        blinking_light(lambda t : new_incoming_message.is_set(),
                       PLAY_KEY, colors[PLAY_KEY], freq=0.25)
        keybow.set_led(PLAY_KEY+3, *[0,0,0])
        keybow.show()


async def record_voice_note():
    while True:
        await recording_message.wait()
        start_time = time.time()
        r = sd.rec(max_recording_time * recording_rate, 
                   samplerate=recording_rate,
                   channels=1, blocking=False)
        logging.info('Recording started')
        cond_f = (lambda t : (recording_message.is_set() and 
                              (t < max_recording_time)))
        blinking_light(cond_f, REC_KEY, colors[REC_KEY])
        message_duration = time.time() - start_time
        logging.info('Recording ended')
        keybow.set_led(REC_KEY+3, *colors[REC_KEY])
        keybow.show()
        wavfile.write('rec.wav', recording_rate, 
                      r[:int(message_duration * recording_rate)])
        a = pydub.AudioSegment.from_file('rec.wav')
        a.export('rec.ogg', format='ogg')
        recording_message.clear()
        new_outgoing_message.set()
        logging.info('Recording done')
        await asyncio.sleep(0.0)


async def send_voice_note(bot):
    while True:
        await new_outgoing_message.wait()
        logging.info(f'Sending voice message to: {target_user}')
        await bot.send_voice(target_user, Path('rec.ogg'))
        logging.info(f'Done sending voice message')
        new_outgoing_message.clear()


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

        a = pydub.AudioSegment.from_file('voice.ogg')
        a = a.apply_gain(amp_correction)
        a.export('voice.wav', format='wav')

        new_incoming_message.set()
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
    inc_volume()

    application = ApplicationBuilder().token(conf['bot']['bot_key']).build()
    
    start_handler = CommandHandler('start', start)
    echo_handler = MessageHandler((filters.TEXT | filters.VOICE | filters.AUDIO) & (~filters.COMMAND), echo)
    log_handler = MessageHandler((~filters.COMMAND), message_log)

    application.add_handler(start_handler)
    application.add_handler(echo_handler)

    async with application:
        await application.start()
        await application.updater.start_polling(telegram_polling_interval)

        send_task = asyncio.create_task(send_voice_note(application.bot))
        incoming_light_task = asyncio.create_task(incoming_light())
        recording_task = asyncio.create_task(record_voice_note())

        await send_task
        await incoming_light_task
        await recording_task

        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
