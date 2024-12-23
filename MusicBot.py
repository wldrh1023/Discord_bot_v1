import discord
from discord.ext import commands
import yt_dlp
import asyncio
from youtubesearchpython import VideosSearch
import random
import json
import os

TOKEN = ''  #디스코드 토큰 입력 부분

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
        'options': '-vn', 'executable': 'ffmpeg',
    }

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.thumbnail = data.get('thumbnail')
        self.webpage_url = data.get('webpage_url')  # 원래 유튜브 비디오 URL 저장


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
    
    #현재 재생중인 곡 정보 저장
    guild_id = str(ctx.guild.id)
    current_song[guild_id] = {
        "title": player.title,
        "url": url,  # 원래 유튜브 링크로 저장
        "thumbnail": player.thumbnail,
        "duration": player.data.get('duration')
    }


# 노래가 끝났을 때 호출되는 함수
async def play_next(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id in queues and queues[guild_id]:
        current_song = queues[guild_id][0]
        await play_song(ctx, current_song)
        queues[guild_id].pop(0)
    else:
        await ctx.send("재생할 노래가 더 이상 없습니다.")
        queues[guild_id] = []

    
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
        
@bot.event
async def on_disconnect():
    save_playlists()
    print("봇이 연결 해제됨: 플레이리스트가 저장되었습니다.")


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

def load_playlists():
    if os.path.exists(PLAYLISTS_FILE):
        with open(PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print("플레이리스트 파일이 손상되어 초기화합니다.")
    print("플레이리스트 파일이 존재하지 않아 새로 생성합니다.")
    return {}

# JSON 파일에 플레이리스트 저장
def save_playlists():
    with open(PLAYLISTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(playlists, f, ensure_ascii=False, indent=4)
        print("플레이리스트가 저장되었습니다.")



#새 플리 생성: new_list [이름]
@bot.command()
async def new_list(ctx, name: str):
    guild_id = str(ctx.guild.id)
    if guild_id not in playlists:
        playlists[guild_id] = {}
        
    if name in playlists[guild_id]:
        await ctx.send(f"이미 '{name}'이라는 이름의 플레이리스트가 존재합니다.")
        return
    
    playlists[guild_id][name] = []
    
    try:
        save_playlists()
        await ctx.send(f"플레이리스트 '{name}'가 성공적으로 생성되었습니다.")
    except Exception as e:
        await ctx.send(f"플레이리스트 저장 중 오류가 발생했습니다: {e}")
        
# 플리 노래 추가: add_list [이름] [노래제목]
@bot.command()
async def add_list(ctx, name: str, *, search: str):
    guild_id = str(ctx.guild.id)  # 서버 ID를 문자열로 변환
    if guild_id not in playlists or name not in playlists[guild_id]:
        await ctx.send("해당1 플레이리스트가 존재하지 않습니다.")
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

    save_playlists()  # JSON 파일 저장
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

        playlist_songs = [song["url"] for song in playlists[guild_id][name]]
        if not playlist_songs:
            await ctx.send(f"플레이리스트 '{name}'에 노래가 없습니다.")
            return
        
        queues[guild_id].extend(playlist_songs)
        await ctx.send(f"플레이리스트 '{name}'가 대기열에 추가되었습니다.")
        
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("먼저 음성 채널에 접속해주세요.")
                return
        
        if not ctx.voice_client.is_playing():
            await play_next(ctx)


# 플리 노래 목록: list_songs
@bot.command()
async def list_songs(ctx, name: str):
    """플레이리스트에 있는 노래 목록을 보여줍니다."""
    guild_id = str(ctx.guild.id)
    if guild_id not in playlists or name not in playlists[guild_id]:
        await ctx.send("해당 플레이리스트가 존재하지 않습니다.")
        return

    song_list = playlists[guild_id][name]
    if not song_list:
        await ctx.send(f"플레이리스트 '{name}'에 노래가 없습니다.")
        return

    song_list_text = "\n".join([f"{idx + 1}. {song['title']} ({song['url']})" for idx, song in enumerate(song_list)])
    await ctx.send(f"플레이리스트 '{name}'에 있는 노래 목록:\n{song_list_text}")



# 플레이 리스트 삭제 명령어: delete_list
@bot.command()
async def delete_list(ctx, name: str):
    guild_id = str(ctx.guild.id)
    if guild_id in playlists and name in playlists[guild_id]:
        del playlists[guild_id][name]
        save_playlists()
        await ctx.send(f"플레이리스트 '{name}'가 삭제되었습니다.")
    else:
        await ctx.send("해당 플레이리스트가 존재하지 않습니다.")

############################################### 플리 ######################################################################## 


# 명령어: stop
@bot.command()
async def stop(ctx):
    """노래를 일시 정지합니다."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("일시 정지되었습니다. 다시 재생하려면 !resume을 입력하세요.")
    else:
        await ctx.send("재생 중인 노래가 없습니다.")

# 명령어: resume
@bot.command()
async def resume(ctx):
    """일시 정지된 노래를 다시 재생합니다."""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("다시 재생됩니다.")
    else:
        await ctx.send("일시 정지된 노래가 없습니다.")

# 명령어: skip
@bot.command(aliases=['s'])
async def skip(ctx):
    """현재 노래를 스킵합니다."""
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("스킵합니다.")
        await play_next(ctx)
    else:
        await ctx.send("재생 중인 노래가 없습니다.")

# 명령어: v (음량 조절)
current_volume = 50

@bot.command()
async def v(ctx, volume: int):
    """음량을 조절합니다."""
    global current_volume
    if ctx.voice_client is None:
        return await ctx.send("봇이 음성 채널에 연결되어 있지 않습니다.")
    
    if volume < 0 or volume > 100:
        return await ctx.send("음량은 0에서 100 사이여야 합니다.")
    
    current_volume = volume
    if ctx.voice_client.source and isinstance(ctx.voice_client.source, discord.PCMVolumeTransformer):
      ctx.voice_client.source.volume = volume / 100
      await ctx.send(f"음량이 {volume}%로 설정되었습니다.")


# 명령어: cv 현재 볼륨 확인
@bot.command()
async def cv(ctx):
    """현재 음량을 확인합니다."""
    await ctx.send(f"현재 음량은 {current_volume}%입니다.")

# 명령어: loop (현재 노래 반복 재생)
@bot.command()
async def loop(ctx):
    """노래를 반복 재생합니다."""
    global loop_song
    loop_song = not loop_song
    await ctx.send(f"노래 반복 재생이 {'활성화' if loop_song else '비활성화'}되었습니다.")



# 명령어: info (현재 노래 정보)
@bot.command()
async def info(ctx):
    if not ctx.voice_client:
        await ctx.send("현재 재생 중인 음악이 없습니다.")
        return

    # 현재 재생 중인 노래 정보
    current_song = ctx.voice_client.source
    if isinstance(current_song, YTDLSource):  # YTDLSource 인스턴스인지 확인
        song_url = current_song.webpage_url if current_song.webpage_url else "URL을 가져올 수 없습니다."
        song_title = current_song.title if current_song.title else "알 수 없음"
        song_duration = current_song.data.get("duration", 0)  # duration이 없으면 0으로 설정
        song_artist = current_song.data.get("uploader", "알 수 없음")

        # duration을 "분:초" 형식으로 변환
        if song_duration == 0:
            song_duration_formatted = "알 수 없음"
        else:
            minutes, seconds = divmod(song_duration, 60)
            song_duration_formatted = f"{minutes}분 {seconds}초"

        # Embed 메시지로 결과 전송
        embed = discord.Embed(title="현재 재생 중인 노래", color=discord.Color.blue())
        embed.add_field(name="제목", value=song_title, inline=False)
        embed.add_field(name="아티스트", value=song_artist, inline=False)
        embed.add_field(name="URL", value=song_url, inline=False)
        embed.add_field(name="길이", value=song_duration_formatted, inline=False)

        await ctx.send(embed=embed)
    else:
        await ctx.send("현재 재생 중인 노래 정보를 찾을 수 없습니다.")

@bot.command()
async def shuffle(ctx):
    if ctx.guild.id in shuffle_enabled and shuffle_enabled[ctx.guild.id]:
        if ctx.guild.id in queues and queues[ctx.guild.id]:
            random.shuffle(queues[ctx.guild.id])
            await ctx.send("대기열이 무작위로 섞였습니다.")
        else:
            await ctx.send("대기열에 노래가 없습니다.")
    else:
        await ctx.send("무작위 재생이 비활성화되어 있습니다. !shuffle_on 명령어를 사용하여 활성화하십시오.")

@bot.command()
async def shuffle_on(ctx):
    shuffle_enabled[ctx.guild.id] = True
    await ctx.send("무작위 재생이 활성화되었습니다. 이제 !shuffle 명령어를 사용하여 대기열을 섞을 수 있습니다.")

@bot.command()
async def shuffle_off(ctx):
    shuffle_enabled[ctx.guild.id] = False
    await ctx.send("무작위 재생이 비활성화되었습니다.")

# 명령어: queue
@bot.command()
async def q(ctx):
    if ctx.guild.id in queues and queues[ctx.guild.id]:
        queue_titles = [await YTDLSource.from_url(url, loop=bot.loop, stream=True) for url in queues[ctx.guild.id]]
        queue_list = "\n".join([f"{idx+1}. {song.title}" for idx, song in enumerate(queue_titles)])
        await ctx.send(f"대기열 목록:\n{queue_list}")
    else:
        await ctx.send("대기열이 비어 있습니다.")
        
# 명령어: reset 
@bot.command()
async def reset(ctx):
    if ctx.guild.id in queues:
        queues[ctx.guild.id] = []  # Clear the queue
        await ctx.send("대기열이 초기화되었습니다.")
    else:
        await ctx.send("대기열이 비어 있습니다.")

###############################################  도움말  ################################################

bot.remove_command("help")

command_descriptions = {
    '!join': '음성 채널에 접속합니다.',
    '!leave': '음성 채널에서 나갑니다.',
    '!p': '유튜브에서 노래를 재생합니다.',
    '!q': '대기열 목록 확인',
    '!reset' : '대기열 초기화',
    '!new_list': '새로운 플레이리스트를 생성합니다.',
    '!add_list': '플레이리스트에 검색어로 여러 노래를 추가합니다.',
    '!play_list': '플레이리스트를 재생합니다.',
    '!list_songs': '플레이리스트에 있는 노래 목록을 보여줍니다.',
    '!delete_list': '플레이리스트를 삭제합니다.',
    '!stop': '현재 노래를 일시 정지합니다.',
    '!resume': '일시 정지된 노래를 다시 재생합니다.',
    '!skip': '현재 노래를 스킵합니다.',
    '!v': '음량을 조절합니다.',
    '!cv': '현재 음량을 확인합니다.',
    '!loop': '노래를 반복 재생합니다.',
    '!info': '현재 재생 중인 곡에 대한 정보를 보여줍니다.',
    '!shuffle': '대기열을 무작위로 섞습니다.',
    '!shuffle_on': '무작위 재생을 활성화합니다.',
    '!shuffle_off': '무작위 재생을 비활성화합니다.'   
}

@bot.command(name='help')
async def help(ctx):
    """사용 가능한 명령어 목록을 보여줍니다."""
    embed = discord.Embed(title="사용 가능한 명령어", color=discord.Color.green())
    
    for command, description in command_descriptions.items():
        embed.add_field(name=f"`{command}`", value=description, inline=False)
    
    await ctx.send(embed=embed)

###############################################  도움말  ################################################

bot.run(TOKEN)
