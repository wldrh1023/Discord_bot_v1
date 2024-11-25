import discord
from discord.ext import commands
import yt_dlp
import asyncio
from youtubesearchpython import VideosSearch
import random
import json
import os

TOKEN = ''  #디스코드 토큰 입력 부분
PLAYLISTS_FILE = 'playlists.json'

intents = discord.Intents.default()   
intents.messages = True 
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 음악 재생을 위한 유틸리티 클래스
YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
    }

FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.thumbnail = data.get('thumbnail')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **FFMPEG_OPTIONS), data=data)

# 노래 재생 함수
async def play_song(ctx, url):
    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        ctx.voice_client.play(player, after=lambda e: bot.loop.create_task(play_next(ctx)))
        
    embed = discord.Embed(title="재생중인노래", description=f"[{player.title}]({url})", color=discord.Color.blue())
    if player.thumbnail:
        embed.set_thumbnail(url=player.thumbnail)
    
    await ctx.send(embed=embed)
    guild_id = ctx.guild.id
    current_song[guild_id] = {
        "title": player.title,
        "url": player.url,
        "thumbnail": player.thumbnail,
        "duration": player.data.get('duration')
    }

# 노래가 끝났을 때 호출되는 함수
async def play_next(ctx):
    if ctx.guild.id in queues and queues[ctx.guild.id]:
        next_song = queues[ctx.guild.id].pop(0)
        await play_song(ctx, next_song)
    else:
        queues[ctx.guild.id] = []
    
# 대기열 및 플레이리스트를 저장하기 위한 딕셔너리
queues = {}
current_song = {} # 노래 정보
playlists = {}  # 서버별 재생목록 저장 딕셔너리
loop_song = False  # 노래 반복 여부
current_volume = 50  # 현재 음량 기본값 50%
shuffle_enabled = {} # 셔플
PLAYLISTS_FILE = 'playlists.json'

# 봇 이벤트
@bot.event
async def on_ready():
    global playlists
    playlists = load_playlists()
    print(f'준비완료 {bot.user.name}')

# 명령어: join
@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect(timeout=60.0)
    else:
        await ctx.send("먼저 음성 채널에 접속해주세요.")

# 명령어: leave
@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.guild.voice_client.disconnect()
    else:
        await ctx.send("봇이 현재 음성 채널에 접속해 있지 않습니다.")

# 명령어: play
@bot.command()
async def p(ctx, *, search: str):
    await handle_song_request(ctx, search)

    # 사용자 음성 채널에 접속
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if ctx.voice_client is None or not ctx.voice_client.is_connected():
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
    else:
        await ctx.send("먼저 음성 채널에 접속해주세요.")
        return

async def handle_song_request(ctx, search: str):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        if ctx.voice_client is None or not ctx.voice_client.is_connected():
            await channel.connect()
        elif ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
    else:
        await ctx.send("먼저 음성 채널에 접속해주세요.")
        return

    # 유튜브 링크 확인
    if "youtube.com/watch" in search or "youtu.be/" in search:
        url = search
        title = "유튜브 링크"  # 유튜브 링크일 때는 타이틀을 설정하지 않음
        thumbnail = None
    else: 
        try:  
            # 노래 제목으로 검색    
            videos_search = VideosSearch(search, limit=5)
            search_result = videos_search.result()
            if 'result' not in search_result or not search_result['result']:
                await ctx.send("검색 결과가 없습니다.")
                return
############################################### 노래 검색 ######################################################################## 
            results = search_result['result']
            embed = discord.Embed(title="검색 결과", color=discord.Color.blue())
            embed.description = ""
            for index, result in enumerate(results):
                embed.add_field(name=f"{index + 1}. [ {result['title']} ]({result['link']})", value=" ", inline=False)

            # 사용자에게 입력 안내 메시지 추가
            embed.description += "\n1~5 중 입력해주세요. 10초간 미입력 시 첫 번째가 재생됩니다."
            await ctx.send(embed=embed)

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit() and 1 <= int(m.content) <= 5
            
            try:
                msg = await bot.wait_for('message', timeout=10.0, check=check)
                selected_index = int(msg.content) - 1
                url = results[selected_index]['link']  # 선택된 URL
                title = results[selected_index]['title']  # 선택된 제목
                thumbnail = results[selected_index]['thumbnails'][0]['url']

                song_info = {
                    'title': title,
                    'url': url,
                    'thumbnail': thumbnail,
                    'duration': result.get('duration', 0),
                }
                current_song[ctx.guild.id] = song_info

            except asyncio.TimeoutError:
                # 시간 초과 시 첫 번째 결과 재생
                url = results[0]['link']
                title = results[0]['title']
                thumbnail = results[0]['thumbnails'][0]['url']
                await ctx.send("시간 초과로 첫 번째 결과를 재생합니다.")

        except asyncio.TimeoutError:    
            url = results[0]['link']
            title = results[0]['title']
            thumbnail = results[0]['thumbnails'][0]['url']

        except Exception as e:
            await ctx.send(f"검색 중 오류가 발생했습니다: {e}")
            return

    # 대기열이 비어 있고 재생 중이 아니면 바로 재생
    if not ctx.voice_client.is_playing():
        await play_song(ctx, url)
    else:
        if ctx.guild.id not in queues:
            queues[ctx.guild.id] = []
        queues[ctx.guild.id].append(url)
        embed = discord.Embed(title="대기중", description=f"[{title}]({url})", color=discord.Color.green())
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        await ctx.send(embed=embed)
############################################### 노래 검색 ######################################################################## 

############################################### 플리 ######################################################################## 

# JSON 파일에서 플레이리스트 불러오기
def load_playlists():
    if os.path.exists(PLAYLISTS_FILE):
        with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("플레이리스트 파일이 손상되어 초기화합니다.")
    print("플레이리스트 파일이 존재하지 않아 새로 생성합니다.")
    return {}

# JSON 파일에 플레이리스트 저장하기
def save_playlists():
    with open(PLAYLISTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(playlists, f, ensure_ascii=False, indent=4)
        print("플레이리스트가 저장되었습니다.")

# 새 플리 생성: new_list [이름]
@bot.command()
async def new_list(ctx, name: str):
    guild_id = str(ctx.guild.id)
    if guild_id not in playlists:
        playlists[guild_id] = {}
    playlists[guild_id][name] = []
    save_playlists()
    await ctx.send(f"플레이리스트 '{name}'가 생성되었습니다.")


# 플리 노래 추가: add_list [이름] [노래제목]
@bot.command()
async def add_list(ctx, name: str, *, search: str):
    guild_id = str(ctx.guild.id)
    if guild_id not in playlists or name not in playlists[guild_id]:
        await ctx.send("해당 플레이리스트가 존재하지 않습니다.")
        return

    searches = [s.strip() for s in search.split(',')]
    added_songs = []

    for search in searches:
        videos_search = VideosSearch(search, limit=1)
        search_result = videos_search.result()
        if 'result' not in search_result or not search_result['result']:
            await ctx.send(f"'{search}'에 대한 검색 결과가 없습니다.")
            continue

        url = search_result['result'][0]['link']
        title = search_result['result'][0]['title']
        playlists[guild_id][name].append({"title": title, "url": url})
        added_songs.append(f"[{title}]({url})")

    save_playlists()
    if added_songs:
        await ctx.send(f"플레이리스트 '{name}'에 다음 노래가 추가되었습니다:\n" + "\n".join(added_songs))
    else:
        await ctx.send(f"플레이리스트 '{name}'에 추가된 노래가 없습니다.")

# 플레이리스트 재생: play_list [이름] [노래제목]
@bot.command()
async def play_list(ctx, name: str):
    guild_id = str(ctx.guild.id)
    if guild_id in playlists and name in playlists[guild_id]:
        if guild_id not in queues:
            queues[guild_id] = []

        queues[guild_id].extend([song["url"] for song in playlists[guild_id][name]])
        await ctx.send(f"플레이리스트 '{name}'가 재생됩니다.")
        
        if not ctx.voice_client.is_playing():
            await play_next(ctx)
    else:
        await ctx.send("해당 플레이리스트가 존재하지 않습니다.")


# 플리 노래 목록: list_songs
@bot.command()
async def list_songs(ctx, name: str):
    """플레이리스트에 있는 노래 목록을 보여줍니다."""
    if ctx.guild.id not in playlists or name not in playlists[ctx.guild.id]:
        await ctx.send("해당 플레이리스트가 존재하지 않습니다.")
        return

    song_list = playlists[ctx.guild.id][name]
    if not song_list:
        await 
