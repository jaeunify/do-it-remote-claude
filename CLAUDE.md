# 프로젝트 메모

Claude Code 원격 작업용 루트 디렉토리.

## 외부 레포 접근
유저가 외부 레포 접근 시도 시 어떤 레포가 있는지 아래 정보를 토대로 확인.

작업 가능한 외부 레포 경로와 용도는 [.claude/settings.local.json](.claude/settings.local.json) 에 정의되어 있음.
- `permissions.additionalDirectories` — 수정 가능한 외부 경로 목록
- `_comment` — 각 경로의 용도 설명