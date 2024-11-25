@echo off
echo Installing required Python modules...

:: 설치할 모듈
pip install discord.py
pip install yt-dlp
pip install asyncio
pip install youtube-search-python
pip install PyNaCl

echo Modules installed successfully!
pause
