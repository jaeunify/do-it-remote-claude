FROM python:3.11-slim

# 시스템 패키지: git, curl(node 설치용), ca-certs, gnupg, node 20
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        ca-certificates \
        gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI (npm 글로벌 — root 권한 필요)
RUN npm install -g @anthropic-ai/claude-code

# 파이썬 의존성
COPY discord-claude-bot/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# 비root 유저 + 작업 디렉토리
RUN useradd -m -u 1000 bot \
    && mkdir -p /workspace \
    && chown bot:bot /workspace

# 봇 코드 + entrypoint
COPY --chown=bot:bot discord-claude-bot/ /home/bot/discord-claude-bot/
COPY --chown=bot:bot entrypoint.sh /home/bot/entrypoint.sh
RUN chmod +x /home/bot/entrypoint.sh

USER bot
WORKDIR /home/bot

ENV WORKSPACE_DIR=/workspace

ENTRYPOINT ["/home/bot/entrypoint.sh"]
