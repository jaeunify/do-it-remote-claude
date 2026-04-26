"""
Claude CLI를 -p (print) 모드로 실행하는 래퍼.
매 요청마다 새 프로세스를 띄우고, --continue로 대화 흐름을 유지한다.
TTY 불필요 — Windows/Linux/macOS 모두 동작한다.
"""

import asyncio
import os
import re
import shutil
import logging

logger = logging.getLogger(__name__)

ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-9;]*[ -/]*[@-~])")
EDIT_INTERVAL = 0.5       # Discord 메시지 edit 최소 간격 (초)
READ_SIZE     = 4096

# 작업 디렉토리 — env 우선, 없으면 claude.py 상위(프로젝트 루트) 사용
# 도커 환경에서는 entrypoint가 WORKSPACE_DIR=/workspace 로 주입한다.
WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)


def _find_claude() -> str:
    # .env의 CLAUDE_PATH 우선, 없으면 PATH에서 탐색
    exe = os.environ.get("CLAUDE_PATH") or shutil.which("claude")
    if not exe:
        raise FileNotFoundError(
            "claude 실행파일을 찾을 수 없습니다. "
            "PATH에 추가하거나 .env에 CLAUDE_PATH=<경로>를 설정하세요."
        )
    return exe


CLAUDE_EXE = _find_claude()


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


class ClaudeProcess:
    def __init__(self):
        self.is_busy  = False
        self._first   = True     # 첫 메시지 여부 (--continue 분기용)
        self._current: asyncio.subprocess.Process | None = None

    # ------------------------------------------------------------------
    # 봇 시작 시 호출 — 이 모드에서는 프리스폰 불필요
    # ------------------------------------------------------------------

    async def spawn(self):
        logger.info("Claude print 모드 준비 완료 (프로세스는 요청마다 실행)")

    def is_alive(self) -> bool:
        return True   # print 모드는 항상 "살아있음"

    async def kill(self):
        if self._current and self._current.returncode is None:
            self._current.kill()
            await self._current.wait()

    # ------------------------------------------------------------------
    # SIGINT — 현재 실행 중인 프로세스에 전달
    # ------------------------------------------------------------------

    def interrupt(self):
        if self._current and self._current.returncode is None:
            import signal, os
            try:
                os.kill(self._current.pid, signal.SIGINT)
                logger.info("SIGINT 전달됨")
            except (ProcessLookupError, PermissionError) as e:
                logger.warning(f"SIGINT 전달 실패: {e}")

    # ------------------------------------------------------------------
    # 스트리밍 응답
    # ------------------------------------------------------------------

    async def stream_response(self, prompt: str):
        """
        claude -p [--continue] "prompt" 를 실행하고 출력을 청크로 yield한다.

        첫 호출은 새 대화, 이후는 --continue로 세션을 이어간다.
        """
        args = [CLAUDE_EXE, "-p"]
        if not self._first:
            args.append("--continue")
        args.append(prompt)

        logger.info(f"claude 실행 (cwd={WORKSPACE_DIR}): {' '.join(args[:3])} ...")

        self._current = await asyncio.create_subprocess_exec(
            *args,
            cwd=WORKSPACE_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._first = False

        # stdout 스트리밍
        assert self._current.stdout is not None
        while True:
            try:
                raw = await asyncio.wait_for(
                    self._current.stdout.read(READ_SIZE),
                    timeout=120.0,
                )
            except asyncio.TimeoutError:
                logger.warning("stream_response: 타임아웃")
                return

            if not raw:
                break

            yield strip_ansi(raw.decode("utf-8", errors="replace"))

        await self._current.wait()

        # 비정상 종료 시 stderr 로깅
        if self._current.returncode != 0:
            assert self._current.stderr is not None
            err = await self._current.stderr.read()
            logger.error(f"claude 종료 코드 {self._current.returncode}: {err.decode(errors='replace')}")
