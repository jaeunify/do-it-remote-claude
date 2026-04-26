#!/bin/bash
set -euo pipefail

# ------------------------------------------------------------------
# 1. git 커밋 작성자
# ------------------------------------------------------------------
git config --global user.email "${GIT_USER_EMAIL:-bot@local}"
git config --global user.name  "${GIT_USER_NAME:-Remote Claude Bot}"

# ------------------------------------------------------------------
# 2. GITHUB_PAT 파싱
#
# 형식: "owner1:token1,owner2:token2"
# 예  : "BLOBLAB217:github_pat_xxx,JAEUNIFY:github_pat_yyy"
# owner 매칭은 case-insensitive (소문자로 정규화).
# ------------------------------------------------------------------
declare -A PAT_MAP
if [ -n "${GITHUB_PAT:-}" ]; then
    IFS=',' read -ra PAIRS <<< "$GITHUB_PAT"
    for raw_pair in "${PAIRS[@]}"; do
        pair="$(echo "$raw_pair" | xargs)"
        [ -z "$pair" ] && continue
        if [[ "$pair" != *:* ]]; then
            echo "[entrypoint] 경고: GITHUB_PAT 항목 형식 오류 (':' 없음): $pair — skip"
            continue
        fi
        key="${pair%%:*}"
        token="${pair#*:}"
        key_lower="$(echo "$key" | tr '[:upper:]' '[:lower:]')"
        PAT_MAP[$key_lower]="$token"
        echo "[entrypoint] PAT 등록됨: owner=${key_lower}"
    done
fi

# ------------------------------------------------------------------
# 3. PLAYGROUND_REPOS 콤마 구분 리스트를 /workspace 아래에 clone
#
# 각 repo URL 의 owner 를 PAT_MAP 에서 찾아서
# https://x-access-token:<PAT>@github.com/<owner>/<repo>.git 으로 clone.
# token 이 .git/config 에 박혀 이후 push 도 자동 인증된다.
# ------------------------------------------------------------------
WORKSPACE="${WORKSPACE_DIR:-/workspace}"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"

if [ -z "${PLAYGROUND_REPOS:-}" ]; then
    echo "[entrypoint] PLAYGROUND_REPOS 미설정 — clone 단계 건너뜀"
else
    IFS=',' read -ra REPOS <<< "$PLAYGROUND_REPOS"
    for raw in "${REPOS[@]}"; do
        repo_url="$(echo "$raw" | xargs)"
        [ -z "$repo_url" ] && continue

        # bash regex 는 lazy quantifier 미지원이라 .git suffix 는 후처리.
        if [[ ! "$repo_url" =~ ^https://github\.com/([^/]+)/([^/]+)$ ]]; then
            echo "[entrypoint] 지원하지 않는 URL 형식: $repo_url — skip"
            continue
        fi
        owner="${BASH_REMATCH[1]}"
        repo_name="${BASH_REMATCH[2]}"
        repo_name="${repo_name%/}"
        repo_name="${repo_name%.git}"

        if [ -d "$repo_name/.git" ]; then
            echo "[entrypoint] $repo_name 이미 clone됨 — skip"
            continue
        fi

        owner_lower="$(echo "$owner" | tr '[:upper:]' '[:lower:]')"
        pat_value="${PAT_MAP[$owner_lower]:-}"

        if [ -z "$pat_value" ]; then
            echo "[entrypoint] 경고: owner=${owner_lower} 에 해당하는 PAT 없음 — public repo 가정하고 clone 시도"
            authed_url="$repo_url"
        else
            authed_url="https://x-access-token:${pat_value}@github.com/${owner}/${repo_name}.git"
            echo "[entrypoint] cloning ${owner}/${repo_name}"
        fi

        git clone "$authed_url" "$repo_name"
    done
fi

# ------------------------------------------------------------------
# 4. 봇 실행
# ------------------------------------------------------------------
cd /home/bot/discord-claude-bot
exec python bot.py
