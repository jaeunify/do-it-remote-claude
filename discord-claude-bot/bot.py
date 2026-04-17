"""
Discord 봇 메인 진입점.

커맨드:
  !ask [prompt]  — Claude에게 질문. 답변을 실시간으로 메시지 Edit.
  !stop          — 진행 중인 작업에 SIGINT 전달.
  !status        — 봇/프로세스 상태 확인.
"""

import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from claude import ClaudeProcess, EDIT_INTERVAL

# ------------------------------------------------------------------
# 설정
# ------------------------------------------------------------------

load_dotenv()

DISCORD_TOKEN: str = os.environ["DISCORD_TOKEN"]
ALLOWED_USER_ID: int = int(os.environ["ALLOWED_USER_ID"])

DISCORD_MAX_LEN = 1990          # Discord 메시지 최대 길이 (2000 - 여유분)
THINKING_MSG = "⏳ 생각 중..."

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 봇 초기화
# ------------------------------------------------------------------

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
claude = ClaudeProcess()


# ------------------------------------------------------------------
# 접근 제한 데코레이터
# ------------------------------------------------------------------

def owner_only():
    """ALLOWED_USER_ID 외의 사용자 차단."""
    async def predicate(ctx: commands.Context) -> bool:
        if ctx.author.id != ALLOWED_USER_ID:
            await ctx.message.add_reaction("🚫")
            return False
        return True
    return commands.check(predicate)


# ------------------------------------------------------------------
# 이벤트 핸들러
# ------------------------------------------------------------------

@bot.event
async def on_ready():
    logger.info(f"봇 로그인 완료: {bot.user} (ID: {bot.user.id})")
    await claude.spawn()
    logger.info("Claude 프로세스 준비 완료")


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    if isinstance(error, commands.CheckFailure):
        return  # owner_only 에서 이미 처리
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ 사용법: `!ask [질문]`")
        return
    logger.error(f"커맨드 오류: {error}", exc_info=error)
    await ctx.send(f"❌ 오류 발생: `{error}`")


# ------------------------------------------------------------------
# !ask 커맨드
# ------------------------------------------------------------------

@bot.command(name="ask")
@owner_only()
async def ask(ctx: commands.Context, *, prompt: str):
    """Claude에게 질문하고 답변을 실시간으로 스트리밍한다."""

    if claude.is_busy:
        await ctx.send("⚠️ 이미 처리 중인 요청이 있습니다. `!stop`으로 중단하거나 잠시 기다려 주세요.")
        return

    claude.is_busy = True
    # 초기 메시지 전송 — 이후 이 메시지를 계속 edit
    message = await ctx.send(THINKING_MSG)

    try:
        await claude.send_prompt(prompt)

        full_response = ""
        last_edit_time = 0.0
        current_message = message   # 2000자 초과 시 새 메시지로 교체

        async for chunk in claude.stream_response():
            full_response += chunk

            now = asyncio.get_event_loop().time()
            if now - last_edit_time >= EDIT_INTERVAL:
                display = _latest_window(full_response)
                try:
                    await current_message.edit(content=display)
                except discord.HTTPException:
                    pass
                last_edit_time = now

            # 2000자 초과 → 새 메시지로 분할
            if len(full_response) > DISCORD_MAX_LEN:
                overflow = full_response[DISCORD_MAX_LEN:]
                await current_message.edit(content=full_response[:DISCORD_MAX_LEN])
                current_message = await ctx.send(overflow[:DISCORD_MAX_LEN] or THINKING_MSG)
                full_response = overflow
                last_edit_time = asyncio.get_event_loop().time()

        # 스트리밍 완료 — 최종 메시지 확정
        final = _latest_window(full_response).strip() or "(응답 없음)"
        await current_message.edit(content=final)

    except Exception as e:
        logger.error(f"!ask 처리 중 오류: {e}", exc_info=e)
        await message.edit(content=f"❌ 오류 발생: `{e}`\n프로세스를 재시작합니다.")
        await claude.kill()
        await claude.spawn()

    finally:
        claude.is_busy = False


# ------------------------------------------------------------------
# !stop 커맨드
# ------------------------------------------------------------------

@bot.command(name="stop")
@owner_only()
async def stop(ctx: commands.Context):
    """진행 중인 Claude 작업에 SIGINT(Ctrl+C)를 전달한다."""
    if not claude.is_busy:
        await ctx.send("ℹ️ 현재 진행 중인 작업이 없습니다.")
        return
    claude.interrupt()
    await ctx.send("🛑 작업 중단 신호를 전송했습니다.")


# ------------------------------------------------------------------
# !status 커맨드
# ------------------------------------------------------------------

@bot.command(name="status")
@owner_only()
async def status(ctx: commands.Context):
    """봇과 Claude 프로세스의 현재 상태를 표시한다."""
    alive = claude.is_alive()
    busy = claude.is_busy
    lines = [
        f"**Claude 프로세스**: {'✅ 실행 중' if alive else '❌ 종료됨'}",
        f"**현재 상태**: {'🔄 처리 중' if busy else '💤 대기 중'}",
    ]
    await ctx.send("\n".join(lines))


# ------------------------------------------------------------------
# 헬퍼
# ------------------------------------------------------------------

def _latest_window(text: str) -> str:
    """Discord 메시지 길이 제한에 맞게 최신 부분을 잘라낸다."""
    if len(text) <= DISCORD_MAX_LEN:
        return text
    return text[-DISCORD_MAX_LEN:]


# ------------------------------------------------------------------
# 진입점
# ------------------------------------------------------------------

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
