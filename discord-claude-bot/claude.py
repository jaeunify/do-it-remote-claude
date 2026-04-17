"""
Claude CLI 프로세스를 asyncio.subprocess로 감싸는 래퍼 클래스.
Windows / Linux / macOS 모두 동작한다.
"""

import asyncio
import re
import logging

logger = logging.getLogger(__name__)

# ANSI 이스케이프 시퀀스 제거
ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-9;]*[ -/]*[@-~])")

# Claude CLI가 입력 대기 중임을 나타내는 프롬프트 패턴
# 실제 출력을 보고 맞지 않으면 조정 필요
PROMPT_RE = re.compile(r"[>❯?]\s*$", re.MULTILINE)

EDIT_INTERVAL = 0.5      # Discord 메시지 edit 최소 간격 (초)
READ_TIMEOUT  = 0.3      # 청크 읽기 타임아웃 (초)
PROMPT_TIMEOUT = 60.0    # 응답 완료 최대 대기 (초)


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


class ClaudeProcess:
    def __init__(self):
        self._process: asyncio.subprocess.Process | None = None
        self.is_busy = False

    # ------------------------------------------------------------------
    # 프로세스 생명주기
    # ------------------------------------------------------------------

    async def spawn(self):
        """claude CLI 프로세스를 비동기 서브프로세스로 실행한다."""
        logger.info("claude 프로세스 시작 중...")
        self._process = await asyncio.create_subprocess_exec(
            "claude", "--dangerously-skip-permissions",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        # 초기 프롬프트가 나올 때까지 버림
        await self._drain_until_prompt(timeout=30.0)
        logger.info("claude 프로세스 준비 완료")

    def is_alive(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def ensure_alive(self):
        """프로세스가 죽어있으면 자동 재시작."""
        if not self.is_alive():
            logger.warning("claude 프로세스가 종료됨. 재시작합니다.")
            await self.spawn()

    async def kill(self):
        if self._process and self._process.returncode is None:
            self._process.kill()
            await self._process.wait()
        self._process = None

    # ------------------------------------------------------------------
    # 입출력
    # ------------------------------------------------------------------

    async def send_prompt(self, prompt: str):
        """프롬프트를 claude에 전송한다."""
        await self.ensure_alive()
        self._process.stdin.write((prompt + "\n").encode())
        await self._process.stdin.drain()

    def interrupt(self):
        """현재 실행 중인 작업에 SIGINT를 전달한다."""
        if self.is_alive():
            import signal, os
            try:
                os.kill(self._process.pid, signal.SIGINT)
                logger.info("SIGINT 전달됨")
            except (ProcessLookupError, PermissionError) as e:
                logger.warning(f"SIGINT 전달 실패: {e}")

    # ------------------------------------------------------------------
    # 비동기 스트리밍
    # ------------------------------------------------------------------

    async def stream_response(self):
        """
        Claude 출력을 비동기 제너레이터로 스트리밍한다.
        프롬프트 패턴 감지 또는 타임아웃 시 종료.

        Yields:
            str: ANSI 제거된 텍스트 청크
        """
        accumulated = ""
        deadline = asyncio.get_event_loop().time() + PROMPT_TIMEOUT

        while asyncio.get_event_loop().time() < deadline:
            try:
                raw = await asyncio.wait_for(
                    self._process.stdout.read(4096),
                    timeout=READ_TIMEOUT,
                )
            except asyncio.TimeoutError:
                # 아직 출력 없음 — 계속 폴링
                if not self.is_alive():
                    logger.warning("claude 프로세스가 예기치 않게 종료됨")
                    return
                continue

            if not raw:
                # EOF
                logger.warning("claude stdout EOF")
                return

            chunk = strip_ansi(raw.decode("utf-8", errors="replace"))
            accumulated += chunk

            # 입력 대기 프롬프트 감지 → 스트리밍 종료
            if PROMPT_RE.search(accumulated):
                final = PROMPT_RE.sub("", accumulated).rstrip()
                if final.strip():
                    yield final
                return

            yield chunk

        logger.warning("stream_response: 타임아웃 초과")

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    async def _drain_until_prompt(self, timeout: float = 30.0):
        """시작 시 초기 출력을 읽어서 버린다."""
        try:
            deadline = asyncio.get_event_loop().time() + timeout
            buf = ""
            while asyncio.get_event_loop().time() < deadline:
                try:
                    raw = await asyncio.wait_for(
                        self._process.stdout.read(4096),
                        timeout=0.5,
                    )
                except asyncio.TimeoutError:
                    continue
                if not raw:
                    return
                buf += strip_ansi(raw.decode("utf-8", errors="replace"))
                if PROMPT_RE.search(buf):
                    return
        except Exception as e:
            logger.warning(f"초기 drain 중 오류 (무시): {e}")
