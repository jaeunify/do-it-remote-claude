# Discord Bot — Claude CLI Wrapper

## Context
로컬 PC에 설치된 Claude Code CLI를 Discord를 중계 서버로 삼아 원격(폰, 외부 PC)에서 사용하기 위한 봇.
Org Policy로 공식 Discord 연동이 막혀 있어서 pexpect로 CLI 프로세스를 직접 제어하는 방식.

## 결정 사항
- **세션**: 전역 단일 세션 (봇 전체가 하나의 claude 프로세스 공유)
- **스트리밍**: 실시간 메시지 Edit (청크마다 Discord 메시지 업데이트)
- **접근 제한**: 단일 USER_ID (본인만 사용)

---

## 파일 구조

```
discord-claude-bot/
├── bot.py          # 메인 봇 코드
├── claude.py       # pexpect 프로세스 관리 클래스
├── .env            # DISCORD_TOKEN, ALLOWED_USER_ID
└── requirements.txt
```

---

## 구현 계획

### 1. `claude.py` — ClaudeProcess 클래스

```
ClaudeProcess
├── spawn()          : pexpect로 claude --dangerously-skip-permissions 실행
├── send(prompt)     : 프롬프트 전송
├── read_chunks()    : async generator — read_nonblocking 루프로 청크 yield
├── interrupt()      : SIGINT 전달 (Ctrl+C)
└── restart()        : 프로세스 종료 감지 시 자동 재시작
```

**프롬프트 종료 감지 방법**: Claude CLI는 응답이 끝나면 특정 프롬프트 문자열(e.g. `> ` 또는 `? `)이 나타남.
`pexpect.expect()`로 이 패턴을 감지해 스트리밍 종료 시점을 판단.

**ANSI 제거**: `re.sub(r'\x1b\[[0-9;]*[mGKHF]', '', text)` 패턴으로 strip.

### 2. `bot.py` — Discord 봇

**슬래시 커맨드 대신 prefix command 사용** (`!ask`, `!stop`)
- slash command는 Discord 앱 등록 + 24h 반영 딜레이 있음
- prefix가 즉시 작동해서 개발/테스트에 유리

```
Commands:
├── !ask [prompt]   : Claude에게 질문 전달 → 실시간 Edit 스트리밍
└── !stop           : 현재 작업에 SIGINT 전달
```

**스트리밍 흐름**:
1. `await ctx.send("⏳ 생각 중...")` 로 초기 메시지 전송 → message 객체 저장
2. `asyncio.create_task()`로 백그라운드에서 Claude 출력 읽기 시작
3. 청크가 쌓일 때마다 (또는 0.5초마다) `await message.edit(content=...)` 호출
4. 2000자 초과 시 자동으로 새 메시지 생성

**보안**: 모든 커맨드 진입 시 `ctx.author.id != ALLOWED_USER_ID` 체크.

### 3. `.env`

```
DISCORD_TOKEN=your_bot_token
ALLOWED_USER_ID=your_discord_user_id
```

### 4. `requirements.txt`

```
discord.py>=2.3.0
pexpect>=4.8.0
python-dotenv>=1.0.0
```

---

## 예외 처리

| 상황 | 처리 |
|------|------|
| claude 프로세스 종료 | `pexpect.EOF` 감지 → 자동 재시작 후 메시지 알림 |
| 응답 중 !stop 실행 | `child.sendintr()` → SIGINT 전달 |
| Discord 2000자 제한 | 자동 청크 분할 후 순차 전송 |
| 동시 !ask 요청 | is_busy 플래그로 중복 실행 차단 |

---

## 검증 방법

1. `python bot.py` 실행 → 봇 온라인 확인
2. `!ask 안녕` → 스트리밍으로 답변 오는지 확인
3. 긴 질문 중 `!stop` → 중단되는지 확인
4. 다른 유저 ID로 시도 → 차단되는지 확인
5. claude 프로세스 강제 종료 후 `!ask` → 자동 재시작 확인
