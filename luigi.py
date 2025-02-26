import discord
from discord.ext import commands
from discord.ext import listening # https://github.com/Sheppsu/discord-ext-listening/tree/main
import asyncio
from random import randint,choice
from gtts import gTTS
import speech_recognition as sr

import time
import os
import concurrent.futures
from pathlib import Path
import threading
from threading import Event
import shutil

import asyncio

intents = discord.Intents().all()
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix='L!', intents=intents)
botToken = "<YOUR BOT TOKEN HERE>"
process_pool = listening.AudioProcessPool(2)
currentVoiceClient = None
shouldExit = Event()
soundsList = ["ciao","citazione","cinghiale","danno","esplosione","limoni","meccaniche","mucche","oro","presidente", "preso", "spaccio", "suono"]
keywordsExclusionList = ["preso", "danno"]
keywordList = [sound for sound in soundsList if sound not in keywordsExclusionList]
quotes = []
recordingsCounter = 0
regularDisconnect = True
savedVoiceChannel = None #Used for reconnecting

MIN_DELAY = 60
MAX_DELAY = 240
MAX_RAND = 69
FILE_FORMATS = {"mp3": listening.MP3AudioFile, "wav": listening.WaveAudioFile}
RECORDINGS_MULT_DIR = True


@bot.command()
async def gnomed(ctx):
    global currentVoiceClient
    global savedVoiceChannel
    global regularDisconnect
    global shouldExit
    global quotes

    #Get quotes
    quotes_channel = bot.get_channel(900765447933272126)
    quotes = [message async for message in quotes_channel.history(limit=1000)]

    #Check if bot is already connected
    voice = ctx.author.voice
    if not voice:
        print("You're not in a vc right now")
        return await ctx.send("You're not in a vc right now")
    else:
        print("Connected to channel")

    #Join the channel and save it for later
    savedVoiceChannel = voice.channel
    currentVoiceClient = await savedVoiceChannel.connect(cls=listening.VoiceClient)

    #Clear any pending events
    shouldExit.clear()
    regularDisconnect = False

    #Start recording
    recording_start(savedVoiceChannel,RECORDINGS_MULT_DIR)

    #Run the random sound func in dedicated Thread pool
    loop = asyncio.get_running_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        await loop.run_in_executor(pool, playRandomDelaySound)

#Randomly choose and update a quote
def updateQuote():
    #Draw a random quote from the channel
    quote = choice(quotes).content
    if quote:
        os.remove("./sounds/citazione.mp3")
        tts = gTTS(text=quote, lang="it", slow=False)
        tts.save("./sounds/citazione.mp3")

#Blocking I/O func dedicated to periodical audio play
def playRandomDelaySound():
    global currentVoiceClient
    global shouldExit
    global quotes

    while not shouldExit.is_set():
        #Update quote
        updateQuote()
        
        #Determine iteration RNG
        suspance = randint(MIN_DELAY, MAX_DELAY)
        dj = randint(0, MAX_RAND)

        #Wait extracted time
        print("Incoming in "+str(suspance)+" seconds")
        shouldExit.wait(suspance)

        #Exit if we need to
        if shouldExit.is_set():
            return

        #Determine which file to play
        file = ""
        if dj < len(soundsList):
            file = f"./sounds/{soundsList[dj]}.mp3"
        else:
            file = "./sounds/gnomed.mp3"
        
        #Play the selected sound
        try:
            currentVoiceClient.play(discord.FFmpegPCMAudio(executable="./bin/ffmpeg", source=file))
        except:
            pass

        shouldExit.wait(5)


async def lookForKeywords(text):
    global currentVoiceClient

    words = text.split()

    for word in words:
        if word in keywordList:
            print("Found word: "+word)

            #Update the quote if needed
            if word == "citazione":
                updateQuote()

            #Play the associate keyword sound
            file = "./sounds/{0}.mp3".format(word)
            try:
                currentVoiceClient.play(discord.FFmpegPCMAudio(executable="./bin/ffmpeg", source=file))
                await asyncio.sleep(5)
            except:
                pass
            return

#Start a recording
def recording_start(channel,useMultipleDirs=False):
    global recordingsCounter

    recordingsPath = "./recordings"

    #Check if we wanna use different folders. This is needed because transcription is slower than recording
    if useMultipleDirs:
        recordingsPath += f"/{recordingsCounter}"
        recordingsCounter += 1
        recordingsCounter = recordingsCounter % 1024
        Path(recordingsPath).mkdir(parents=True, exist_ok=True)

    #Start listening
    currentVoiceClient.listen(
        listening.AudioFileSink(FILE_FORMATS["wav"], recordingsPath),
        process_pool,
        after=recording_end_callback,
        channel=channel
    )

#Transcribe files
async def recording_end_worker(sink, folderNumber):
    
    rec = sr.Recognizer()
    recordingsFolder = ""

    #Check if we recorded anything
    if len(sink.output_files.items()) == 0:
        recordingsFolder = f"./recordings/{folderNumber}"

    #Format and recognize speech
    for ssrc,audioFile in sink.output_files.items():
        if recordingsFolder == "":
            recordingsFolder = os.path.dirname(os.path.realpath(audioFile.path))
        #Attempt speech recognition on the WAV
        with sr.AudioFile(audioFile.path) as source:
            try:
                audio_data = rec.record(source)
                srtext = rec.recognize_google(audio_data,language="it-IT").lower()
                text = "SR: " + srtext
                print(text)
                #If we got some text, look for the keywords
                await lookForKeywords(text)
            except:
                pass
        #Cleanup
        os.remove(audioFile.path)
    #Remove folder
    if recordingsFolder != "":
        shutil.rmtree(recordingsFolder)

#Stop recording, convert audio files, launch transcribing, then restart recording
async def recording_end_callback(sink, exc=None, channel=None):
    global shouldExit

    #Quit instead if the bot should be stopped
    if shouldExit.is_set():
        await sink.vc.disconnect()
        return

    #Convert text here due to cross-process usage
    start_time = time.time()
    sink.convert_files()
    await sink.wait_for_convert()
    print("Conversion took: %s seconds" % (time.time() - start_time))

    #Transcribe text
    t = threading.Thread(target=asyncio.run,args=(recording_end_worker(sink,recordingsCounter-1),))
    t.daemon = True
    t.start()

    #Restart recording
    recording_start(channel,RECORDINGS_MULT_DIR)

#Poll the recording if the bot is connected
async def pollAudio():
    global shouldExit
    global savedVoiceChannel
    global currentVoiceClient

    while True:
        if not regularDisconnect and currentVoiceClient not in bot.voice_clients:
            print("Anomalous disconnect detected, attempting reconnect")
            await attemptReconnect()
            recording_start(savedVoiceChannel,RECORDINGS_MULT_DIR)
        elif currentVoiceClient:
            if not shouldExit.is_set():
                currentVoiceClient.stop_listening()
            print("Sleeping for 15 seconds")
        await asyncio.sleep(15)

#Disconnect bot
@bot.command()
async def solong(ctx):
    global shouldExit
    global currentVoiceClient
    global savedVoiceChannel
    global regularDisconnect
    
    if ctx.voice_client is None:
        print("Im not in a channel ")
        return
    
    shouldExit.set()
    ctx.voice_client.stop_listening()
    await ctx.voice_client.disconnect()
    currentVoiceClient = None
    savedVoiceChannel = None
    regularDisconnect = True
    print("Luigi successfully disconnected")


#Keyboard interrupt handler
def quit(signo, _frame):
    global shouldExit

    shouldExit.set()
    exit()

async def attemptReconnect():
    global currentVoiceClient
    global regularDisconnect

    print("Attempting reconnection...")
    currentVoiceClient = await savedVoiceChannel.connect(cls=listening.VoiceClient)
        

@bot.event
async def on_ready():
    global shouldExit

    print('We have logged in as {0.user}'.format(bot))
    shouldExit.set()
    await pollAudio()

if __name__ == '__main__':

    import signal
    for sig in ('TERM', 'INT'):
        signal.signal(getattr(signal, 'SIG'+sig), quit);

    bot.run(botToken)
