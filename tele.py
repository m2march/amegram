#!/usr/bin/env python
import RPi.GPIO as GPIO  
import keybow
import logging
import time
import datetime
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
import soundfile as sf

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

CONVERTION_ALPHA = 0.3
OFF_ALPHA = 0.3

colors = {
    REC_KEY : REC_COLOR,
    MID_KEY : MID_COLOR,
    PLAY_KEY : PLAY_COLOR,
}

sd.default.device = [0, 1]
recording_rate = 44100
max_recording_time = 10 * 60
target_user = 76053031 #"@M2March"
amp_correction = 1#9
telegram_polling_interval = 0.5
volume_options = [10, 30, 50, 70, 90, 100]
current_volume_idx = 2

new_outgoing_message = asyncio.Event()
new_incoming_message = asyncio.Event()
recording_message = asyncio.Event()
start_message_playback = asyncio.Event()

@keybow.on()
def handle_key(index, state):
    if state:
        if index == PLAY_KEY:
            logging.info('Play key')
            start_message_playback.set()
        elif index == REC_KEY:
            if recording_message.is_set():
                logging.info('Finishing recording')
                recording_message.clear()
            else:
                logging.info('Recording sound')
                recording_message.set()
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


async def blinking_light(cond_f, key, color_arr, freq=2, sleep_time=0.1):
    start_time = time.time()
    passed_time = time.time() - start_time
    while (cond_f(passed_time)):
        key_alpha = (np.cos(passed_time * freq * (2 * np.pi)) + 1) / 2
        key_color = adjust_color_alpha(color_arr, key_alpha)
        keybow.set_led(key+3, *key_color)
        keybow.show()
        await asyncio.sleep(sleep_time)
        passed_time = time.time() - start_time


async def message_playback(context):
    while True:
        logging.info('Started job: "message_playback"')
        await start_message_playback.wait()
        new_incoming_message.clear()
        logging.info('Playing sound')
        sr, d = wavfile.read('voice.wav')
        sd.play(d, samplerate=sr, blocking=False)
        await blinking_light(lambda t: t < d.shape[0] / sr,
                             PLAY_KEY, colors[PLAY_KEY], 2)
        logging.info('Playback done')
        start_message_playback.clear()
        #context.job_queue.run_once(message_playback, 0.1)


async def record_voice_note(context):
    while True: 
        logging.info('Started job: "record_voice_note"')
        await recording_message.wait()
        logging.info('Recording pre-started')
        start_time = time.time()
        r = sd.rec(max_recording_time * recording_rate, 
                   samplerate=recording_rate,
                   channels=1, blocking=False)
        logging.info('Recording started')
        cond_f = (lambda t : (recording_message.is_set() and 
                              (t < max_recording_time)))
        await blinking_light(cond_f, REC_KEY, colors[REC_KEY])
        message_duration = time.time() - start_time
        logging.info('Recording ended')
        keybow.set_led(REC_KEY+3, *adjust_color_alpha(colors[REC_KEY],
                                                      CONVERTION_ALPHA))
        keybow.show()
        wavfile.write('rec.wav', recording_rate, 
                      r[:int(message_duration * recording_rate)])

        data, samplerate = sf.read('rec.wav')
        sf.write('rec.ogg', data, samplerate, format='OGG', subtype='VORBIS')
        recording_message.clear()
        new_outgoing_message.set()
        logging.info('Recording done')
        keybow.set_led(REC_KEY+3, *adjust_color_alpha(colors[REC_KEY], 1))
        keybow.show()


async def incoming_light(context):
    while True:
        logging.info('Started job: "incoming_light"')
        await new_incoming_message.wait()
        logging.info('New message: blinking incoming light')
        await blinking_light(lambda t : new_incoming_message.is_set(),
                             PLAY_KEY, colors[PLAY_KEY], freq=0.25)
        keybow.set_led(PLAY_KEY+3, *adjust_color_alpha(colors[PLAY_KEY], OFF_ALPHA))
        keybow.show()


async def send_voice_note(context):
    await new_outgoing_message.wait()
    logging.info(f'Sending voice message to: {target_user}')
    await context.bot.send_voice(target_user, Path('rec.ogg'))
    logging.info(f'Done sending voice message')
    new_outgoing_message.clear()
    context.job_queue.run_once(send_voice_note, 0.1)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f'Message: {update.message}')
    print(update.message.voice)
    if update.message.voice is not None:
        logging.info(f'Voice from:{update.message.from_user} :: {update.message.voice.duration}s')

        if update.message.from_user.id == target_user:
            file_id = update.message.voice.file_id
            new_file = await context.bot.get_file(file_id)
            await new_file.download_to_drive('voice.ogg')

            data, samplerate = sf.read('voice.ogg')
            sf.write('voice.wav', data, samplerate)

            new_incoming_message.set()
    else:
        logging.info(f'Message from:{update.message.from_user} :: {update.message.text}')
        keybow.set_led(MID_KEY+3, *colors[MID_KEY])
        keybow.show()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=update.message.text)
        await asyncio.sleep(10)
        keybow.clear()
        keybow.show()

async def message_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f'Message: {update.message}')

async def voice_echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info(f'Voice from:{update.message.from_user} :: {update.message.audio.duration}s')


async def post_init(application):
    loop = asyncio.get_event_loop() 
    #loop.create_task(send_voice_note())
    loop.create_task(incoming_light(None))
    loop.create_task(record_voice_note(None))
    loop.create_task(message_playback(None))
    #td = datetime.timedelta(hours=0, seconds=1)
    application.job_queue.run_once(send_voice_note, 1)
    #application.job_queue.run_once(incoming_light, td)
    #application.job_queue.run_once(record_voice_note, td)
    #application.job_queue.run_once(message_playback, td)


def main():
    conf = configparser.ConfigParser()
    conf.read('tele.conf')

    application = (ApplicationBuilder().token(conf['bot']['bot_key'])
                   .post_init(post_init).build())
    
    start_handler = CommandHandler('start', start)
    echo_handler = MessageHandler((filters.TEXT | filters.VOICE | filters.AUDIO) & (~filters.COMMAND), echo)
    log_handler = MessageHandler((~filters.COMMAND), message_log)

    application.add_handler(start_handler)
    application.add_handler(echo_handler)

    logging.info(time.asctime())

    keybow.set_led(REC_KEY+3, *colors[REC_KEY])
    keybow.set_led(PLAY_KEY+3, *adjust_color_alpha(colors[PLAY_KEY], OFF_ALPHA))
    keybow.show()
    inc_volume()
    
    application.run_polling()

if __name__ == '__main__':
    main()
