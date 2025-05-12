#!/usr/bin/env python
import RPi.GPIO as GPIO  
import keybow
import time
import os
import subprocess

colors = {
    0:[40, 150, 20],
    1:[0, 0, 255],
    2:[255, 0, 0],
}

sounds = {
    0:"hh1.mp3",
    1:"hh2.mp3",
    2:"hh3.mp3",
}

play_sound = None
playing_sound = None

import pygame
import time

# Initialize the pygame mixer
# The mixer module is required for sound playback
pygame.mixer.init()

def play_sound(path):
	try:
	    # Load the sound file
	    sound = pygame.mixer.Sound(path)

	    # Play the sound
	    print(f"Playing sound: {path}")
	    sound.play()

	    time.sleep(sound.get_length() + 1) # Wait for the sound duration plus 1 second

	except pygame.error as e:
	    print(f"Error loading or playing sound: {e}")
	    print(f"Please ensure the file '{sound_file_path}' exists and is a valid WAV or OGG file.")

	finally:
	    # Quit the mixer
	    # This is important for releasing resources
	    pygame.mixer.quit()
	    print("Pygame mixer quit.")

rec_key = 6
play_key = 0
is_rec = False

@keybow.on()
def handle_key(index, state):
    global play_sound, is_rec
    print("{}: Key {} has been {}".format(
        time.time(),
        index,
        'pressed' if state else 'released'))

    re_index = index // 3

    p = None

    if state:
        if index == rec_key:
            p = subprocess.Popen(["arecord", "rec.wav"])
            print('Starting to record')
            is_rec = True
        elif index == play_key:
            try:
                p = subprocess.Popen(["mplayer", "rec.wav"])
            except ValueError as ve:
                print(ve)
    else:
        if index == rec_key:
            p.terminate()
            is_rec = False 
            print('Done recording')

for i, c in colors.items():
    keybow.set_led((i+1) * 3, *c)

while True:
    keybow.show()
    time.sleep(1.0 / 60.0)
