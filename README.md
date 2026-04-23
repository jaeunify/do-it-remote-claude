# Remote Claude via Discord

## 1. 소개

지하철... 출근길... 정말 심심해요.
아까 하던 개발이 아른거려요...

![심심한 출근길](resources/manwha_1.jpg)

원격...!! 원격이라도 하자!!
(폰 화면으로 PC 화면 원격) 으악 !!! 왜 이렇게 글자가 작아 !!! 아직 나이도 어린데 !!

![원격 화면의 공포](resources/manwha_2.jpg)

잠깐 !!!! 당신을 위한, **Remote Claude** !
이제 언제 어디서나, 디스코드로 코딩하세요!

![Remote Claude 등장](resources/manwha_3.jpg)

---

## 2. 환경

| 항목 | 내용 |
|------|------|
| Python | 3.11 이상 |
| Claude Code CLI | 로컬 PC에 설치되어 있어야 함 |
| Discord Bot | Developer Portal에서 봇 생성 필요 |
| OS | Windows / Linux / macOS |

---

## 3. 세팅 방법

### 1) 봇 생성

1. [Discord Developer Portal](https://discord.com/developers/applications)에서 새 앱 생성
2. Bot 탭 → 토큰 발급 (`DISCORD_TOKEN`)
3. Message Content Intent 활성화
4. 봇을 서버에 초대 (권한: Send Messages, Read Messages)

### 2) 프로젝트 설정

```bash
cd discord-claude-bot
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3) `.env` 파일 작성

`discord-claude-bot/.env` 파일을 만들고 아래 내용을 채운다.

```env
DISCORD_TOKEN=your_bot_token_here
ALLOWED_USER_ID=your_discord_user_id_here

# (선택) claude 실행파일이 PATH에 없을 경우
# CLAUDE_PATH=C:\Users\yourname\AppData\Roaming\npm\claude.cmd
```

> Discord 유저 ID 확인: Discord 설정 → 고급 → 개발자 모드 ON → 본인 프로필 우클릭 → "사용자 ID 복사"

### 4) 실행

```bash
# Windows (PowerShell)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
venv\Scripts\activate
py bot.py
```

---

## 4. 사용법

봇이 온라인 상태일 때 Discord에서 아래 커맨드를 입력한다.

| 커맨드 | 설명 |
|--------|------|
| `!ask [질문]` | Claude에게 질문. 답변이 실시간으로 메시지에 업데이트됨 |
| `!stop` | 진행 중인 작업에 Ctrl+C를 전달해 중단 |
| `!status` | 봇과 Claude 프로세스의 현재 상태 확인 |

응답은 Discord 메시지를 실시간으로 Edit하는 방식으로 스트리밍된다.
2000자를 초과하면 자동으로 메시지를 분할한다.

---

## 5. 반전

사실 **Claude Code의 원격 세션 기능**을 쓰면 그냥 됩니다.

이건 그냥 Discord 봇 커스텀하고 싶어서 만든 거예요 ㅋㅋ

---

## 6. 무엇을 할 수 있나요?

Claude에게 코드 작업을 시키고 자동으로 `git push`되도록 설정해두면, **GitHub Pages 배포 결과를 폰으로 바로 확인**할 수 있어요. 일단은 이 정도로 활용 중입니다.

```
폰 Discord → !ask → 로컬 Claude Code → git push → GitHub Pages 반영
```
