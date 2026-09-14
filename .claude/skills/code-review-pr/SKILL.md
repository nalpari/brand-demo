---
name: code-review-pr
description: '이 저장소에 올라온 PR 을 빌트인 code-review 로 리뷰하되, CLAUDE.md 의 프로젝트 규칙(테스트 정책, okf/ 동기화, MyBatis 규약, Spring Boot 4 이름, 보안 정책)을 명시적 체크 축으로 얹어 팀원 전원이 같은 기준으로 보게 한다. "PR 리뷰해줘", "PR 번호로 리뷰", "#123 리뷰", "머지 전 확인해줘", "이 PR 문제 없는지 봐줘", "코드리뷰 돌려줘" 처럼 PR 검토를 요청하면 반드시 이 스킬을 쓴다. 빌트인 리뷰만 부르면 프로젝트 고유 규칙 위반은 아무도 잡지 않는다.'
---

# PR 리뷰

빌트인 `/code-review` 를 이 저장소 규칙에 맞춰 부르는 래퍼다.

**왜 래퍼인가:** 빌트인 리뷰는 일반적인 버그와 단순화만 본다. 이 저장소 고유 규칙 — 테스트가 어디 살아야 하는지, `okf/` 를 같은 변경에서 갱신했는지 — 은 그 축에 없어서 아무도 잡지 않는다. 팀원마다 PR 을 보는 기준이 다른 것도 같은 문제의 다른 얼굴이다. 이 스킬은 기준을 하나로 고정한다.

## 1. 대상 PR 확정

PR 번호는 필수다. **추측하지 않는다.** 못 받았으면 목록을 보여주고 묻는다.

```bash
gh pr list --limit 20
```

번호가 정해지면 메타를 확인한다.

```bash
gh pr view <n> --json number,title,url,baseRefName,headRefName,additions,deletions,changedFiles
```

사용자에게 한 줄로 보고한다:

```
#123 "주문 취소 API 추가" — feature/order-cancel → main, 파일 8개 +342/-17
```

리뷰가 시작되기 전에 사용자가 대상을 확인할 수 있어야 한다. 번호를 잘못 들었으면 여기서 끝난다.

## 2. 빌트인 code-review 호출

```
Skill(skill: "code-review", args: "high 123")
```

호출할 것은 빌트인 `code-review` 다. 플러그인의 `code-review:code-review` 나 `coderabbit:code-review` 는 다른 도구이고 인자 규약도 다르다.

인자 규칙 — 어기면 조용히 틀린다:

- **순서는 `<effort> <target>` 고정.** 첫 토큰이 effort 로 소비된다. `"123 high"` 는 123 을 effort 로 먹는다.
- **effort 기본은 `high`.** 사용자가 가볍게 보자고 하면 `low`/`medium`, 더 넓게 보자고 하면 `max`.
- **target 은 PR 번호 / 브랜치명 / 파일 경로 셋 중 하나만.** `/code-review` 는 target 을 검증하지 않는다. 문장이나 설명("주문 API PR 좀 봐줘")을 넘기면 **에러 없이** 기본 범위인 현재 브랜치 diff 를 리뷰한다. 결과는 그럴듯하게 나오고 아무도 눈치채지 못한다. 넘기기 전에 target 이 번호 하나인지 눈으로 확인한다.
- **`ultra` 를 부르지 마라.** 사용자만 트리거할 수 있고 별도 과금된다. 필요해 보이면 `/code-review ultra <n>` 을 직접 치라고 안내한다.
- **`--comment` / `--fix` 는 사용자가 명시적으로 요청했을 때만.** `--comment` 는 PR 에 인라인 코멘트를 등록한다 — 팀 전체에 보이는 외부 행위다. `--fix` 는 워킹 트리를 고친다. 기본은 터미널 출력뿐이다.

## 3. 프로젝트 규칙 축 얹기 — 이 래퍼의 존재 이유

호출 전에 저장소 루트의 `CLAUDE.md` 를 읽는다. 그리고 아래 다섯 축 각각에 대해, PR diff 에 해당하는 변경이 있으면 그 축의 위반 여부를 명시적 체크 항목으로 리뷰에 얹는다.

**규칙 내용은 여기 적지 않는다.** CLAUDE.md 가 유일한 원본이고, 여기 복사본을 두면 CLAUDE.md 가 바뀔 때 조용히 어긋난다. 이 표에 있는 건 *무엇을 봐야 하는지*와 *어디에 적혀 있는지*뿐이다.

| 축 | CLAUDE.md 절 | diff 에 이게 있으면 본다 |
|---|---|---|
| 테스트 정책 | `Testing: TDD, service layer only` | 새/수정된 테스트, 새 서비스·컨트롤러 로직 |
| okf/ 번들 동기화 | `Knowledge bundle (okf/)` | 테이블 DDL, 매퍼 SQL, 엔드포인트 시그니처, 시큐리티 설정 |
| MyBatis 규약 | `MyBatis conventions` | `*Mapper.java`, `mapper/*.xml`, 결과 매핑 POJO |
| Spring Boot 4 패키지·스타터 | `Spring Boot 4 package/starter moves` | `build.gradle`, 새 import, 테스트 애노테이션 |
| 보안 정책 | `Security` | 시큐리티 설정, 익명 허용 경로·메서드, 토큰 클레임, CSRF·세션 |

축이 diff 와 무관하면 건너뛴다. 없는 위반을 만들어 채우면 진짜 지적이 그 안에 묻힌다.

**보안 축만은 결론이 "변경 없음"이어도 한 줄 남긴다.** 보안 정책이 바뀌었는지 아닌지는 PR 을 읽는 사람이 알아야 할 사실이고, 침묵은 "확인 안 함"과 구분되지 않는다.

## 4. 결과 정리

빌트인이 돌려준 findings 를 심각도순 표 하나로 합친다. 원문을 그대로 이어 붙이지 않는다.

```markdown
## PR #123 리뷰 — "주문 취소 API 추가"

**지적 4건** — Critical 1 / Important 2 / Minor 1

| # | 심각도 | 위치 | 문제 | 해결 방안 |
|---|--------|------|------|-----------|
| 1 | Critical | `OrderService.java:88` | 취소 후 재고 복구 누락 | 같은 트랜잭션에서 `restoreStock` 호출 |
| 2 | Important | `OrderMapper.xml:41` | `keyColumn` 없음 | `keyProperty` 옆에 `keyColumn` 추가 |

### 프로젝트 규칙

| 축 | 결과 |
|---|---|
| 테스트 정책 | OrderServiceTest 3건 추가, 위반 없음 |
| okf/ 동기화 | ⚠️ 엔드포인트 추가됐으나 `okf/api/orders.md` 미갱신 |
| MyBatis 규약 | ⚠️ 위 지적 #2 |
| Spring Boot 4 | 해당 없음 |
| 보안 정책 | 변경 없음 |
```

- 위치는 반드시 `파일:줄`. "주문 로직 부근" 은 위치가 아니다.
- 규칙 표에는 **다섯 축이 전부 나온다.** "해당 없음"과 "확인 안 함"은 다른 말이고, 빈칸이 있으면 읽는 사람은 후자를 의심한다.
- 지적이 0건이면 findings 표는 생략하고 한 줄로 쓴다. 규칙 표는 그래도 남긴다.

## 하지 말 것

- PR 번호 추측하기. "최근 거겠지" 로 남의 PR 을 리뷰하게 된다.
- args 에 문장 넘기기. 조용히 현재 브랜치를 리뷰하고 결과는 멀쩡해 보인다.
- `ultra` 부르기. 사용자 트리거 전용이고 과금된다.
- 시키지 않은 `--comment`. PR 코멘트는 팀 전체에 보이고 지워도 알림은 이미 갔다.
- 시키지 않은 `--fix`. 리뷰 결과를 보는 것과 반영하는 것은 별개의 결정이다.
- CLAUDE.md 규칙을 이 파일로 옮겨 적기. 두 벌이 되는 순간 한 벌은 틀린다.
