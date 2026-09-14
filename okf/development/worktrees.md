---
type: Development Procedure
title: Worktrees
description: Creating, entering, configuring, and removing an explicitly requested worktree.
tags: [development, git, worktrees]
generated: { by: claude-code/opus-5, at: 2026-09-11T07:02:03Z }
status: draft
---

# Worktrees

생성 조건, 플랫폼별 경로, 디렉터리·브랜치 이름 규칙은
[CLAUDE.md](../../CLAUDE.md#worktrees)를 따른다.

`EnterWorktree`를 그냥 호출하면 위치가 저장소 안 `.claude/worktrees/`로 고정되어 [CLAUDE.md의 경로 규칙](../../CLAUDE.md#worktrees)을 지킬
수 없다. 직접 만든 뒤 `path`로 진입한다:

아래는 macOS / Linux용 예시이고, 저장소 루트(`brand/`의 상위)에서 실행한다. Windows에서는
CLAUDE.md의 Windows 경로를 사용한다.

```bash
git fetch -q origin
git ls-remote --heads origin <포켓몬>    # 출력이 비어 있어야 사용 가능

WT=~/.worktrees/eland/<관광명소>
git worktree add "$WT" -b <포켓몬> origin/main

# 버전관리 안 되는 설정 파일을 옮긴다. 없는 파일은 건너뛴다.
for f in brand/.env brand/.env.local brand/src/main/resources/application-local.yaml; do
  [ -f "$f" ] || continue
  mkdir -p "$WT/$(dirname "$f")"
  cp -p "$f" "$WT/$f"
done
```

그 다음 `EnterWorktree`에 그 경로를 `path`로 넘긴다.

**워크트리에서도 서버가 떠야 하므로 추적하지 않는 설정 파일은 같이 복사한다.** 지금 해당하는
것은 `brand/.env` 하나다 — `JWT_SECRET` 이 거기 있고, `application.yaml` 이
`optional:file:.env[.properties]` 로 읽는다. 빠뜨리면 워크트리에서만 부팅마다 임의 키가 생성되고
(`WARN` 한 줄이 전부다) 앞선 워크트리에서 받은 토큰이 전부 검증에 실패한다 — 서버는 멀쩡히 뜨므로
증상이 시크릿을 가리키지 않는다. `brand/src/main/resources/application.yaml` 은 추적 중이라 그대로
딸려온다. **추적하지 않는 설정 파일을 추가하면 같은 변경에서 위 목록에도 넣는다.**

**브랜치 이름은 만들기 전에 반드시 원격과 대조한다.** 이미 있으면 다른 포켓몬을 고른다. 로컬에
같은 이름이 있어도 `git worktree add -b`가 실패하므로 마찬가지로 다른 이름으로 간다.

이렇게 진입한 워크트리는 `ExitWorktree`가 지우지 못한다(`keep`만 가능). 작업이 끝나면
`git worktree remove <경로>`로 직접 정리한다.
