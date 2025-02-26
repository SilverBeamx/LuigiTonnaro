# LuigiTonnaro
Repo for LuigiTonnaro, an homebrewed Discord bot that plays sounds at random intervals in a voice call and listens for keywords to optionally play those sounds on demand.
The bot includes a function to use TTS to replay messages sent in a specific channel of your choosing, mainly meant for Quotes.

This repo includes a "libs" folder that includes some custom modified python libraries. These libraries should be deployed in a virtual environment, overwriting the publicly available ones.

Discord.py package should be installed with voice support(discord[voice]).

Bring your own ffmpeg executable and place it into the bin directory.

Bring your own sounds in mp3 format and place them into the sounds directory. Configure which sounds you want to play by editing the first lines of the script.

Make your own Discord Bot key and edit the botToken variable. Change the channel id to one of your choosing for the Quotes (or disable it altogether).
