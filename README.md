1. VS코드와 파이썬 3.9.0 을 설치
   https://code.visualstudio.com/Download#
   https://www.python.org/ftp/python/3.9.0/python-3.9.0-amd64-webinstall.exe
2. 모듈 설치파일을 실행
3. FFMPEG 파일을 다운로드
   https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip
   바탕화면에 압축풀기
   ffmpeg 실행파일까지 들어가서 경로 복사
   예시) C:\Users\User\Desktop\ffmpeg\bin
5. 윈도우키 - 고급 시스템 설정(검색) - 환경 변수 - 시스템 변수 부분 Path클릭 - 편집 - 새로만들기 - 복사했던 경로 붙혀넣기 - 확인
6. https://discord.com/developers/applications 접속
7. New Application - 이름 설정
8. 왼쪽 OAuth2 설정 - SCOPES부분 bot 체크, BOT PERMISSIONS부분 Administrator(관리자 권한)체크 - GENERATED URL부분 Copy버튼 - 인터넷창 주소 복붙 - 원하는 서버에 초대
9. 왼쪽 BOT 설정 - TOKEN부분 Reset Token - 토큰 복사 - 노래봇코드로 가서 토큰에 붙혀넣기
   ex) TOKEN = 'ajsdkljfalksjdlfadf' - 바깥에 쉼표 (') 있는지 확인
10. 밑에 설정 더 내려가서 Privileged Gateway intents 세개 다 활성화, PUBLIC BOT (공개봇임 아무나 쓸수있는거) 원하면 활성화, 나만쓸거면 비활성화
11. vs코드로 코드 복붙후 토큰확인하고 실행
12. !help 명령어 확인

주의 사항 ![image](https://github.com/user-attachments/assets/0351bf43-8ef4-4fe6-aeac-8f7ca115f606) 인터프리터가 Python으로 설정되어있는지 실행후 터미널에서 확인
Python으로 설정이 안되어있다면 Ctrl + Shift + P 입력 - Select interpreter 타이핑후 엔터 - 인터프리터 리스트중 Python 3.9.0 클릭 또는 다른버전의 Python 클릭
![image](https://github.com/user-attachments/assets/fae1f726-49eb-48cd-9b39-3c80d3cd0c6c)


