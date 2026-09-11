# SPAO 브랜드몰 DB 스키마 (IA 기반 TO-BE 초안)

출처: [`docs/ref/IA(FO,BO)_스파오(1).xlsx`](../ref/) — FO/BO 시트, 2026-01-07 기준 메뉴 구성도.

**상태: 제안.** 아래 테이블은 아직 DB에 없고 `okf/tables/`에도 없다. 실제 스키마의 기준은
언제나 [`okf/tables/`](../../okf/tables/index.md)이며, 이 문서는 메뉴 구성도가 요구하는 데이터를
먼저 그려 본 설계 초안이다. 테이블을 실제로 만들 때는 CLAUDE.md의 절차대로 DDL을 DB에 적용하고
`okf/tables/<table>.md`를 쓴 뒤 이 문서의 해당 항목을 그쪽 링크로 바꾼다.

## 읽는 법

- 메뉴 구성도의 화면이 **조회·저장하는 데이터**를 엔티티로 뽑았다. 레이어·버튼·링크 같은 화면 흐름은 테이블이 아니다.
- 외부 시스템이 소유하는 데이터는 테이블로 만들지 않고 식별자만 둔다: 리뷰(크리마), 챗봇(채널톡), AI 추천(AWS Personalize), 과거 주문(카페24), 라이브, PG.
- 모든 테이블에 `created_at timestamptz not null default now()`, `updated_at timestamptz`가 있다고 보고 목록에서 생략했다.
- 표기: `PK` 기본키, `→ table` 외래키, `UQ` 유일, `?` NULL 허용. 타입은 PostgreSQL.
- 상태값(`status`, `*_type`)은 `common_code`로 관리하되 여기서는 후보 값을 괄호 안에 적었다.

## ERD

| 파일 | 범위 |
|---|---|
| [erd-overview.html](erd-overview.html) | 도메인 간 관계 — 8개 애그리거트 루트 |
| [erd-member.html](erd-member.html) | 회원과 회원이 소유하는 것 |
| [erd-product.html](erd-product.html) | 상품 · 단품 · 업체 · 표준 분류 · 매장 재고 |
| [erd-display.html](erd-display.html) | 전시 코너 구성 · 배너 · 기획전 · 스냅 · 컬래버 IP |
| [erd-order.html](erd-order.html) | 주문 · 배송 · 혜택 · 클레임 · 결제 · 환불 |
| [erd-promotion.html](erd-promotion.html) | 프로모션 · 쿠폰 · 이벤트 응모/당첨 |
| [erd-settlement.html](erd-settlement.html) | 결제 · 포인트 · 정산 · 채널 |
| [erd-system.html](erd-system.html) | BO 사용자 · 역할 · 메뉴 · URL 권한 |

고객지원·검색·시스템 코드성 테이블(8, 9절)은 관계가 거의 없는 평면 테이블이라 다이어그램에 넣지 않았다.

ERD HTML과 이 문서의 HTML 판([`erd-schema.html`](erd-schema.html))은 [`erd-gen.py`](erd-gen.py)가 만든다.
스키마가 바뀌면 HTML을 손으로 고치지 말고 이 마크다운과 스크립트의 스펙(엔티티·그리드·관계)을 고친 뒤
`python3 docs/diagrams/erd-gen.py`로 다시 생성한다. 스크립트는
그리는 컬럼이 이 문서에 있는지, 연결선이 겹치거나 상자를 가로지르지 않는지 검사하고 실패하면 파일을 쓰지 않는다.

## 설계 메모

- **쿠폰은 프로모션의 한 종류다.** BO 프로모션 등록 메뉴가 즉시할인·더블쿠폰·장바구니쿠폰·배송비쿠폰·사은품을 한 화면에서 다루므로 `promotion` 하나에 `promo_type`으로 구분하고, 회원에게 발급된 것만 `member_coupon`으로 분리했다.
- **전시 코너 항목은 다형 참조다.** 코너 하나가 배너·카테고리·상품·기획전·스냅·IP·HTML을 섞어 담으므로 `display_corner_item.item_type + item_id`로 가리킨다. DB 외래키는 걸 수 없고 서비스에서 검증한다.
- **비회원 주문은 `orders.member_id`가 NULL**이고 `guest_*` 컬럼으로 조회한다. 별도 비회원 테이블은 없다.
- **포인트는 원장(ledger)이다.** 스파오포인트·이포인트, 적립·사용·소멸·미가용을 `point_ledger` 한 테이블의 행으로 기록하고 잔액은 합산한다.
- **클레임(취소·교환·반품)은 한 테이블**이고 `claim_type`으로 나눈다. 매장픽업 반품은 `pickup_shop_id`가 채워진 반품이다.
- **매장(shop)과 업체(vendor)는 다르다.** 매장은 SPAO 오프라인 점포(재고 조회·픽업·단골), 업체는 상품 공급사(계약·정산)다.

---

## 1. 회원 (member)

### member — 회원
IA: FO 공통 › 회원가입·로그인·비밀번호 변경·회원 탈퇴 철회 · 마이페이지 › 계정정보 › 회원정보 · 오프라인 매장안내 › 단골매장 등록 · APP 마케팅 수신동의 · BO 회원관리, 상담관리 › CTI › 회원선택

```
id                     bigserial     PK
login_id               text          UQ
password_hash          text
name                   text
phone                  text
email                  text?
birth_date             date?
gender                 char(1)?
grade_code             text          회원등급 (common_code)
status                 text          ACTIVE / WITHDRAW_PENDING / WITHDRAWN
favorite_shop_id       bigint?       → shop  단골매장
marketing_agree        boolean
password_changed_at    timestamptz?  장기 미변경 판단
withdraw_requested_at  timestamptz?  탈퇴 철회 가능 기간 판단
```

### member_address — 배송지
IA: 마이페이지 › 계정정보 › 배송지 관리 (조회·등록·수정·삭제)

```
id          bigserial  PK
member_id   bigint     → member
alias       text
recipient   text
phone       text
zip         text
address1    text
address2    text?
is_default  boolean
```

### member_child — 우리 아이정보
IA: 마이페이지 › 계정정보 › 우리 아이정보 (MY_31)

```
id          bigserial  PK
member_id   bigint     → member
name        text
birth_date  date
gender      char(1)?
```

### member_device — 앱 기기·푸시 설정
IA: APP 앱 설정 › 푸시알림 설정 · 컬래버레이션 › 오픈알림설정 · 이벤트 › 푸시 수신동의

```
id            bigserial    PK
member_id     bigint       → member
os            text         IOS / ANDROID
device_token  text         UQ
push_agree    boolean
last_seen_at  timestamptz
```

### member_terms_agreement — 약관 동의
IA: 회원가입 · 주문서 약관동의 · Footer 이용약관/개인정보처리방침

```
id          bigserial    PK
member_id   bigint       → member
terms_code  text         SERVICE / PRIVACY / MARKETING / ORDER
agreed      boolean
agreed_at   timestamptz
```

### wishlist — 찜
IA: 마이페이지 › 활동 정보 › 찜하기 (상품·스냅·콜라보 좋아요, MY_21~23) · Bottom Navi › 찜하기

```
id           bigserial  PK
member_id    bigint     → member
target_type  text       PRODUCT / SNAP / COLLAB_IP
target_id    bigint     다형 참조
UQ (member_id, target_type, target_id)
```

### recent_view — 최근 본 상품
IA: 마이페이지 › 활동 정보 › 최근 본 상품 (MY_24~25)

```
id          bigserial    PK
member_id   bigint       → member
product_id  bigint       → product
viewed_at   timestamptz
UQ (member_id, product_id)
```

### restock_alert — 재입고 알림 신청
IA: 상품상세 › 재입고알림 · 마이페이지 › 재입고 알림 신청내역 › 해제 · BO 상품조회/수정 › 재입고알림내역조회

```
id              bigserial     PK
member_id       bigint        → member
product_sku_id  bigint        → product_sku
status          text          WAITING / NOTIFIED / CANCELED
notified_at     timestamptz?
```

## 2. 업체·매장 (vendor, shop)

### vendor — 업체
IA: BO 업체관리 › 업체 › 하위업체조회·하위업체등록·업체조회

```
id                bigserial  PK
parent_vendor_id  bigint?    → vendor  하위업체
code              text       UQ
name              text
business_no       text
vendor_type       text       FASHION / JEWELRY
status            text
```

### vendor_contract — 업체 계약
IA: BO 업체관리 › 하위업체 계약정보조회(패션/주얼리)

```
id               bigserial     PK
vendor_id        bigint        → vendor
contract_no      text
start_date       date
end_date         date?
commission_rate  numeric(5,2)
status           text
```

### vendor_return_pickup — 반품자동수거 서비스
IA: BO 업체관리 › 반품자동수거 서비스 신청·수정

```
id              bigserial    PK
vendor_id       bigint       → vendor
courier_code    text
pickup_address  text
is_active       boolean
applied_at      timestamptz
```

### vendor_color / vendor_size — 업체 색상·사이즈
IA: BO 상품기초정보관리 › 업체색상/사이즈관리. 업체 코드를 표준 코드에 매핑한다.

```
id            bigserial  PK
vendor_id     bigint     → vendor
code          text
name          text
std_color_id  bigint     → std_color   (vendor_size 는 std_size_id → std_size)
UQ (vendor_id, code)
```

### shop — 오프라인 매장
IA: FO 오프라인 매장안내 › 매장 검색·검색결과 (GP_04) · 상품상세 › 매장찾기 · 장바구니 › 매장픽업 조회/변경 · BO 업체관리 › 매장 › 매장조회

```
id          bigserial      PK
code        text           UQ
name        text
phone       text?
zip         text
address     text
lat         numeric(9,6)
lng         numeric(9,6)
open_hours  text?
pickup_yn   boolean        매장픽업 가능
status      text
```

### shop_stock — 매장 재고
IA: 상품상세 › 매장재고조회 · 매장찾기 (POS 재고 동기화)

```
shop_id         bigint       → shop
product_sku_id  bigint       → product_sku
qty             integer
synced_at       timestamptz
PK (shop_id, product_sku_id)
```

## 3. 상품 (product)

### std_category — 표준 카테고리
IA: BO 업체관리 › 표준카테고리 조회 · 상품등록의 분류

```
id          bigserial  PK
parent_id   bigint?    → std_category
name        text
depth       smallint
sort_order  integer
```

### std_color / std_size — 표준 색상·사이즈
IA: BO 상품기초정보관리 › 표준색상/사이즈관리

```
id          bigserial  PK
code        text       UQ
name        text
hex         char(7)?   std_color 만
sort_order  integer    std_size 만
```

### product — 상품
IA: FO 상품상세 (/i/item) · BO 상품관리 › 상품등록(연동/단독/일반/사은품)·상품조회/수정·일괄수정

```
id                bigserial  PK
vendor_id         bigint     → vendor
std_category_id   bigint     → std_category
product_code      text       UQ
name              text
product_type      text       NORMAL / GIFT
source_type       text       LINKED / STANDALONE   연동상품 vs 단독상품
list_price        integer
sale_price        integer
sale_status       text       ON_SALE / SOLD_OUT / STOPPED
display_yn        boolean
description_html  text?
notice_id         bigint?    → product_notice
```

### product_sku — 단품
IA: 상품상세 › 옵션선택 · 검색 › 바코드 스캔 · BO 상품조회/수정 › 단품/재고확인·단품정보일괄수정

```
id            bigserial  PK
product_id    bigint     → product
sku_code      text       UQ
barcode       text?      UQ  바코드/QR 스캔
std_color_id  bigint     → std_color
std_size_id   bigint     → std_size
add_price     integer    옵션 추가금
stock_qty     integer
sale_status   text
```

### product_image — 상품 이미지

```
id          bigserial  PK
product_id  bigint     → product
sort_order  integer
url         text
```

### product_price_history — 가격 이력
IA: BO 상품조회/수정 › 가격이력(단독상품)·가격변경

```
id          bigserial    PK
product_id  bigint       → product
list_price  integer
sale_price  integer
changed_by  bigint       → bo_user
changed_at  timestamptz
```

### product_flag — 상품 플래그
IA: BO 상품부가정보관리 › 플래그관리 (BEST / NEW / SALE 등 뱃지)

```
id          bigserial     PK
product_id  bigint        → product
flag_code   text          common_code
start_at    timestamptz?
end_at      timestamptz?
```

### product_selling_point — 셀링포인트
IA: BO 상품부가정보관리 › 셀링포인트관리

```
id          bigserial  PK
product_id  bigint     → product
sort_order  integer
content     text
```

### product_attribute — 상품 속성
IA: BO 상품기초정보관리 › 상품 속성 관리 · FO 검색필터

```
id          bigserial  PK
product_id  bigint     → product
attr_code   text       common_code
attr_value  text
```

### product_info_disclosure — 상품정보제공고시
IA: BO 상품기초정보관리 › 상품정보제공고시관리 · 상품등록 › 상품제공고시 조회

```
id             bigserial  PK
product_id     bigint     → product
template_code  text       품목별 고시 템플릿
items          jsonb      항목/값
```

### product_notice — 상품 공지
IA: BO 상품부가정보관리 › 상품공지사항관리 › 등록/수정

```
id        bigserial     PK
title     text
content   text
start_at  timestamptz?
end_at    timestamptz?
```

## 4. 전시 (display)

### display_category — 전시 카테고리
IA: FO 카테고리 (우먼/맨/키즈/컬래버 › 중카테고리 › `dispCategoryNo`) · 햄버거메뉴 › 대/중카테고리 · BO 전시카테고리관리 › 기본카테고리·IP 카테고리

```
id             bigserial  PK
parent_id      bigint?    → display_category
category_type  text       BASIC / IP
home_type      text       WOMEN / MEN / KIDS / COLLAB
collab_ip_id   bigint?    → collab_ip   IP 카테고리일 때
name           text
depth          smallint
sort_order     integer
display_yn     boolean
```

### display_category_product — 전시 카테고리 상품
IA: BO 전시카테고리관리 › 상품 조회 레이어

```
display_category_id  bigint   → display_category
product_id           bigint   → product
sort_order           integer
PK (display_category_id, product_id)
```

### collab_ip — 컬래버레이션 IP
IA: FO 컬래버레이션 › 라인업·런칭캘린더·신상 · BO 전시코너 › 컬래버레이션 라인업 › 추천 IP목록

```
id           bigserial  PK
name         text
logo_url     text
launch_date  date?      런칭캘린더
status       text
```

### display_corner — 전시 코너
IA: BO 전시컨텐츠관리 › 전시코너구성관리 › 홈매장(우먼/맨/키즈/컬래버 홈 메인배너, 마케팅 팝업, 햄버거메뉴 퀵메뉴·상단/하단 컨셉 카테고리, 브랜드소개, 회원혜택) · 유닛매장(기간할인, 포유, 컬래버 라인업, 컬래버 신상, 기획전 목록, 스타일링 클립)

```
id           bigserial     PK
store_type   text          HOME / UNIT
home_type    text?         WOMEN / MEN / KIDS / COLLAB
corner_code  text          MAIN_BANNER / POPUP / QUICK_MENU / TOP_CONCEPT / BOTTOM_CONCEPT / SALE_BANNER / FORYOU_BANNER / IP_LINEUP / COLLAB_NEW_INFO / PLANSHOP_LIST / RECOMMEND_SNAP / SNAP_LIST / BRAND_ABOUT / MEMBER_BENEFIT
name         text
display_yn   boolean
start_at     timestamptz?
end_at       timestamptz?
UQ (store_type, home_type, corner_code)
```

### display_corner_item — 코너 항목
IA: 각 코너의 배너조회·카테고리 조회·상품 조회·스냅 조회·기획전 조회 레이어

```
id                 bigserial     PK
display_corner_id  bigint        → display_corner
item_type          text          BANNER / CATEGORY / PRODUCT / PLANSHOP / SNAP / IP / HTML
item_id            bigint?       다형 참조 (HTML 은 NULL)
html               text?         item_type = HTML
sort_order         integer
start_at           timestamptz?
end_at             timestamptz?
```

### banner — 배너
IA: BO 전시컨텐츠관리 › 배너관리 › 배너 등록 레이어 · 홈 마케팅팝업

```
id                bigserial     PK
name              text
image_url         text
mobile_image_url  text?
link_url          text?
alt_text          text?
start_at          timestamptz?
end_at            timestamptz?
display_yn        boolean
created_by        bigint        → bo_user
```

### planshop — 기획전
IA: FO 기획전 › 목록·상세 (기본형·영상형·HTML 모듈) · BO 전시컨텐츠관리 › 기획전관리

```
id             bigserial     PK
title          text
template_type  text          BASIC / VIDEO / HTML
thumbnail_url  text
video_url      text?
html           text?
start_at       timestamptz
end_at         timestamptz?
status         text
```

### planshop_product — 기획전 상품
IA: BO 기획전관리 › 상품 조회 레이어

```
planshop_id  bigint   → planshop
product_id   bigint   → product
section      text?    기본형 모듈 섹션
sort_order   integer
PK (planshop_id, product_id)
```

### snap — 스타일링 클립
IA: FO 퀵메뉴 › 스타일링 클립·상세 (/u/snap) · BO 전시컨텐츠관리 › 스냅관리 › 등록/수정 · 전시코너 › 추천스냅·스냅목록(WOMEN/MEN/KIDS)

```
id            bigserial     PK
title         text
gender_type   text          WOMEN / MEN / KIDS
media_type    text          IMAGE / VIDEO
media_url     text
like_count    integer       wishlist(SNAP) 집계 캐시
status        text
published_at  timestamptz?
```

### snap_product — 스냅 태그 상품
IA: BO 스냅관리 › 상품 조회 레이어

```
snap_id     bigint   → snap
product_id  bigint   → product
sort_order  integer
PK (snap_id, product_id)
```

### notice — 공지사항
IA: FO 마이페이지 › ABOUT SPAO › 공지사항 목록·상세 · 홈 공지사항 · BO 전시컨텐츠관리 › 공지사항관리 · 시스템관리 › 공지사항

```
id         bigserial     PK
audience   text          FO / BO
title      text
content    text
is_pinned  boolean
start_at   timestamptz?
end_at     timestamptz?
```

### static_page — 정적 HTML 페이지
IA: Footer › 브랜드소개 (GP_03, HTML 에디터) · 회원혜택 (GP_10) · BO 전시코너 › 브랜드소개·회원혜택 html

```
code        text     PK   BRAND_ABOUT / MEMBER_BENEFIT
title       text
html        text
updated_by  bigint   → bo_user
```

### app_splash — 앱 스플래시
IA: FO 공통 › 스플래시 (GP_01) · BO 전시컨텐츠관리 › 앱 스플래시 이미지관리

```
id          bigserial     PK
image_url   text
start_at    timestamptz?
end_at      timestamptz?
display_yn  boolean
```

## 5. 주문 (order)

### cart_item — 장바구니
IA: FO 주문 › 장바구니 (옵션변경·매장픽업 조회/변경·배송방식 변경)

```
id              bigserial  PK
member_id       bigint?    → member
guest_key       text?      비회원 세션 키
product_sku_id  bigint     → product_sku
qty             integer
delivery_type   text       PARCEL / PICKUP
pickup_shop_id  bigint?    → shop
```

### orders — 주문
IA: FO 주문서(일반배송·매장픽업·비회원)·주문완료 · 마이페이지 › 주문내역 조회·주문 상세 · 비회원 주문조회 · BO 주문관리 › 주문조회·주문상세조회WP·매장픽업 주문조회

```
id                   bigserial     PK
order_no             text          UQ
member_id            bigint?       → member   NULL = 비회원
guest_name           text?
guest_phone          text?
guest_password_hash  text?         비회원 주문조회
channel_id           bigint?       → channel
order_type           text          DELIVERY / PICKUP
status               text          ORDERED / PAID / PREPARING / SHIPPING / DELIVERED / CANCELED
pickup_shop_id       bigint?       → shop
item_amount          integer
discount_amount      integer
delivery_fee         integer
pay_amount           integer
terms_agreed_at      timestamptz
ordered_at           timestamptz
```

### order_item — 주문 상품
IA: 주문상세 › 상품정보 · BO 주문관리 › 상품준비중처리·선출고처리·주문상품이력

```
id               bigserial  PK
order_id         bigint     → orders
product_sku_id   bigint     → product_sku
product_name     text       주문 시점 스냅샷
option_name      text
qty              integer
unit_price       integer
discount_amount  integer
status           text       ORDERED / PREPARING / SHIPPING / DELIVERED / CANCELED / RETURNED / EXCHANGED
promised_date    date?      약속일등록
pre_shipped      boolean    선출고
```

### order_delivery — 배송
IA: 주문서 › 배송정보 · 마이페이지 › 배송조회 · BO 배송관리 › 출고배송관리(배송준비중·배송중·배송완료·송장 일괄 수정)·배송지연상세현황 · 주문상세 › 배송희망일변경

```
id            bigserial     PK
order_id      bigint        → orders
seq           smallint      분할 배송 순번
recipient     text
phone         text
zip           text
address1      text
address2      text?
request_memo  text?
wish_date     date?
courier_code  text?
invoice_no    text?
status        text          READY / PREPARING / SHIPPING / DELIVERED
shipped_at    timestamptz?
delivered_at  timestamptz?
```

### order_benefit — 주문 적용 혜택
IA: 주문서 › 할인정보·쿠폰 적용 · BO 주문상세 › 주문혜택·주문변경혜택 · 프로모션 사은품 지급내역

```
id                bigserial  PK
order_id          bigint     → orders
order_item_id     bigint?    → order_item   NULL = 주문 단위 혜택
benefit_type      text       COUPON / POINT / PROMOTION / CARD / GIFT
member_coupon_id  bigint?    → member_coupon
promotion_id      bigint?    → promotion
gift_product_id   bigint?    → product
amount            integer
```

### order_memo — 주문 메모
IA: BO 주문상세조회WP › 고객메모·상담정보

```
id          bigserial  PK
order_id    bigint     → orders
memo_type   text       CUSTOMER / CS
content     text
bo_user_id  bigint?    → bo_user
```

### claim — 클레임 (취소·교환·반품)
IA: FO 마이페이지 › 취소신청·교환신청·반품신청·매장픽업반품신청·취소/교환/반품내역 · BO 주문관리 › 취소/반품/교환접수WP·교환품절 · 클레임관리 › 반품관리(반품확인·완료·보류)·교환관리

```
id              bigserial     PK
claim_no        text          UQ
order_id        bigint        → orders
claim_type      text          CANCEL / EXCHANGE / RETURN
status          text          REQUESTED / ACCEPTED / HOLD / COLLECTING / COMPLETED / REJECTED
reason_code     text
reason_text     text?
pickup_shop_id  bigint?       → shop   매장픽업 반품
courier_code    text?         회수 송장
invoice_no      text?
requested_at    timestamptz
completed_at    timestamptz?
```

### claim_item — 클레임 상품

```
id               bigserial  PK
claim_id         bigint     → claim
order_item_id    bigint     → order_item
qty              integer
exchange_sku_id  bigint?    → product_sku   교환 시 새 단품
sold_out         boolean    교환품절
```

### bulk_order_request — 대량구매 신청
IA: FO Footer › 대량구매 신청 (GP_06~08) · 마이페이지 › 대량구매신청내역·상세 · BO 주문관리 › 대량주문 조회/관리

```
id               bigserial     PK
member_id        bigint        → member
company          text
contact_name     text
phone            text
email            text
request_content  text
wish_qty         integer?
wish_date        date?
status           text          REQUESTED / REVIEWING / QUOTED / CLOSED
answered_at      timestamptz?
```

### offline_order / offline_order_item — 오프라인 주문 (POS 연동)
IA: FO 마이페이지 › 오프라인 주문 내역 조회·주문 상세 · BO 주문관리 › 오프라인 주문조회

```
offline_order
  id            bigserial    PK
  member_id     bigint       → member
  shop_id       bigint       → shop
  receipt_no    text         UQ
  total_amount  integer
  purchased_at  timestamptz

offline_order_item
  id                bigserial  PK
  offline_order_id  bigint     → offline_order
  product_sku_id    bigint?    → product_sku
  qty               integer
  unit_price        integer
```

## 6. 결제·포인트·정산 (payment, point, settlement)

### payment — 결제
IA: 주문서 › 결제수단 · BO 주문상세 › 결제정보 · 결제관리 › 조회업무관리 › 결제로그 조회

```
id           bigserial     PK
order_id     bigint        → orders
pay_method   text          CARD / BANK / VBANK / EASY / POINT
pg_code      text?
pg_tid       text?         UQ
card_code    text?
amount       integer
status       text          APPROVED / CANCELED / PARTIAL_CANCELED / FAILED
approved_at  timestamptz?
canceled_at  timestamptz?
```

### payment_log — 결제 로그
IA: BO 결제관리 › 결제로그 조회 · 결제취소오류 재전송(재전송·수기처리)

```
id          bigserial  PK
payment_id  bigint     → payment
event       text       APPROVE / CANCEL / RESEND / MANUAL
request     jsonb?
response    jsonb?
success     boolean
```

### refund — 환불
IA: BO 결제관리 › 환불관리 › 환불요청 관리 (계좌인증·승인·승인취소·타행이체 불능조회·계좌이체·환불완료)

```
id                bigserial     PK
claim_id          bigint        → claim
payment_id        bigint        → payment
amount            integer
refund_method     text          PG_CANCEL / BANK_TRANSFER
bank_code         text?
account_no        text?
account_holder    text?
account_verified  boolean
status            text          REQUESTED / APPROVED / TRANSFER_FAILED / COMPLETED / CANCELED
processed_by      bigint?       → bo_user
processed_at      timestamptz?
```

### point_ledger — 포인트 원장
IA: FO 마이페이지 › 혜택정보 › 포인트 (스파오포인트·이포인트, 적립·미가용 내역) · BO 회원혜택관리 › 혜택수동지급 › 스파오포인트 · 정산관리 › 비용조회 › 통합/스파오포인트사용내역

```
id             bigserial     PK
member_id      bigint        → member
point_type     text          SPAO / EPOINT
tx_type        text          EARN / USE / CANCEL / EXPIRE
amount         integer       사용·소멸은 음수
balance_after  integer
available_at   timestamptz?  미가용 → 가용 전환 시각
expires_at     timestamptz?
order_id       bigint?       → orders
reason         text
issued_by      bigint?       → bo_user   수동지급
```

### settlement — 정산
IA: BO 정산관리 › 매출정산 › 매출정산조회·국세청 판매대행 신고서 · 결제 정산 › 승인내역대사·입금내역대사 (SAP전송/취소) · 비용조회 › 채널/프로모션 정산내역

```
id           bigserial     PK
settle_type  text          SALES / APPROVAL / DEPOSIT
settle_date  date
vendor_id    bigint?       → vendor
channel_id   bigint?       → channel
amount       integer
status       text          DRAFT / CONFIRMED / SENT_SAP / CANCELED
sap_sent_at  timestamptz?
```

### settlement_line — 정산 명세
IA: 결제안분다운·결제 배분 로그·상품 매출/혜택/비용 생성 결과

```
id             bigserial  PK
settlement_id  bigint     → settlement
order_id       bigint?    → orders
payment_id     bigint?    → payment
line_type      text       SALE / FEE / POINT / PROMOTION / SHIPPING
amount         integer
```

### settlement_job_log — 정산 작업 로그
IA: BO 정산관리 › 정산로그 › 정산 작업 현황·생성/처리 결과·샵링크·Flink 전송 결과

```
id           bigserial     PK
job_type     text
started_at   timestamptz
finished_at  timestamptz?
status       text          RUNNING / SUCCESS / FAILED
message      text?
```

## 7. 마케팅 (promotion, event)

### channel — 채널
IA: BO 마케팅관리 › 채널관리 › 채널조회·등록

```
id            bigserial  PK
code          text       UQ
name          text
channel_type  text       SALES / INFLOW
use_yn        boolean
```

### promotion — 프로모션
IA: BO 마케팅관리 › 프로모션관리 › 프로모션 등록(즉시할인·더블쿠폰·장바구니쿠폰·배송비쿠폰·상품사은품·주문사은품)·승인 · FO 상품상세 › 쿠폰받기

```
id                bigserial     PK
name              text
promo_type        text          INSTANT_DISCOUNT / DOUBLE_COUPON / CART_COUPON / SHIPPING_COUPON / PRODUCT_GIFT / ORDER_GIFT
discount_type     text?         RATE / AMOUNT
discount_value    integer?
min_order_amount  integer?
max_discount      integer?
gift_product_id   bigint?       → product   사은품
channel_id        bigint?       → channel
start_at          timestamptz
end_at            timestamptz?
status            text          DRAFT / APPROVED / ACTIVE / ENDED
approved_by       bigint?       → bo_user
approved_at       timestamptz?
```

### promotion_target — 프로모션 적용 대상

```
id            bigserial  PK
promotion_id  bigint     → promotion
target_type   text       ALL / PRODUCT / CATEGORY / MEMBER_GRADE
target_id     bigint?    다형 참조
```

### coupon_code — 쿠폰 코드
IA: BO 프로모션 등록 › 쿠폰코드 등록 · FO 마이페이지 › 쿠폰 › 인증번호로 등록 · 이벤트 › 혜택코드

```
id            bigserial     PK
promotion_id  bigint        → promotion
code          text          UQ
max_issue     integer?
issued_count  integer
expires_at    timestamptz?
```

### member_coupon — 발급 쿠폰
IA: FO 마이페이지 › 혜택정보 › 쿠폰 (온라인·오프라인) · 주문서 › 쿠폰 적용 · BO 회원혜택관리 › 혜택수동지급 › 쿠폰·지급내역 조회

```
id              bigserial     PK
member_id       bigint        → member
promotion_id    bigint        → promotion
coupon_code_id  bigint?       → coupon_code
use_channel     text          ONLINE / OFFLINE
issue_source    text          DOWNLOAD / CODE / EVENT / MANUAL
status          text          ISSUED / USED / EXPIRED
issued_at       timestamptz
expires_at      timestamptz?
used_at         timestamptz?
order_id        bigint?       → orders
```

### event — 이벤트
IA: FO 이벤트 › 목록·상세 (EV_01~02) · 마이페이지 › 이벤트게시판(참여현황) · BO 이벤트관리 › 이벤트등록 (자동응모: 첫구매·구매사은·첫로그인·신규가입·친구초대·제휴링크 / 수동클릭응모: 응모조건없음·구매사은·출석체크·푸시 수신동의·댓글·정답형·혜택코드·SNS공유)·복사등록·출석체크 관리

```
id              bigserial     PK
title           text
entry_mode      text          AUTO / MANUAL
entry_type      text          FIRST_PURCHASE / PURCHASE_GIFT / FIRST_LOGIN / SIGNUP / INVITE / AFFILIATE_NEW / AFFILIATE_EXISTING / NO_CONDITION / ATTENDANCE / PUSH_AGREE / COMMENT / QUIZ / BENEFIT_CODE / SNS_SHARE
event_html_id   bigint?       → event_html
start_at        timestamptz
end_at          timestamptz?
status          text
copied_from_id  bigint?       → event   복사등록 원본
```

### event_html — 이벤트 HTML
IA: BO 이벤트관리 › 이벤트 HTML 관리 › 조회·등록

```
id    bigserial  PK
name  text
html  text
```

### event_entry — 이벤트 응모
IA: BO 이벤트관리 › 이벤트 응모관리 › 선택등수처리 · 출석체크는 일자별 응모 행

```
id          bigserial    PK
event_id    bigint       → event
member_id   bigint       → member
entry_data  text?        댓글 / 정답 / 혜택코드
entered_at  timestamptz
rank        smallint?
```

### event_winner — 이벤트 당첨
IA: BO 이벤트관리 › 이벤트 당첨관리 › 선택 당첨취소·선택 지급완료·메일발송·SMS발송

```
id              bigserial     PK
event_id        bigint        → event
event_entry_id  bigint        → event_entry
member_id       bigint        → member
rank            smallint
prize_type      text          COUPON / POINT / GIFT
prize_ref_id    bigint?       promotion.id 등 다형 참조
status          text          WON / PAID / CANCELED
mail_sent_at    timestamptz?
sms_sent_at     timestamptz?
```

### payment_benefit — 카드·결제수단 혜택
IA: BO 마케팅관리 › 카드혜택 등록 · 결제수단 혜택관리

```
id            bigserial     PK
pay_method    text
card_code     text?
benefit_type  text          INSTALLMENT / DISCOUNT
description   text
start_at      timestamptz
end_at        timestamptz?
```

### affiliate_link — 제휴링크
IA: BO 마케팅관리 › 제휴링크 관리 › 등록/수정 · 이벤트 › 제휴링크 신규/기존회원

```
id            bigserial  PK
code          text       UQ
name          text
partner_name  text
landing_url   text
event_id      bigint?    → event
```

### seo_meta — 전시몰 메타
IA: BO 마케팅관리 › SEO 관리 › SEO 외부 수집 XML·전시몰 메타관리

```
id           bigserial  PK
page_type    text       HOME / CATEGORY / PRODUCT / PLANSHOP / EVENT
page_id      bigint?
title        text
description  text?
keywords     text?
```

## 8. 고객지원·검색 (cs, search)

### inquiry — 1:1 문의
IA: FO 마이페이지 › 나의 문의 내역 › 조회·등록 (/m/qna) · BO 상담관리 › 문의관리 › 고객상담관리

```
id             bigserial     PK
member_id      bigint        → member
order_id       bigint?       → orders
product_id     bigint?       → product
category_code  text
title          text
content        text
status         text          OPEN / ANSWERED / CLOSED
answer         text?
answered_by    bigint?       → bo_user
answered_at    timestamptz?
```

### faq — 자주 묻는 질문
IA: FO 고객센터 › 자주 묻는 질문 · BO 상담관리 › 탬플릿관리 › 사이트 FAQ등록/조회

```
id             bigserial  PK
category_code  text
question       text
answer         text
sort_order     integer
use_yn         boolean
```

### consultation — 상담 기록 (CTI)
IA: BO 상담관리 › CTI › 회원선택·상담현황 · 주문상세 › CTI·상담정보

```
id            bigserial    PK
member_id     bigint?      → member
order_id      bigint?      → orders
bo_user_id    bigint       → bo_user
channel       text         PHONE / CHAT
content       text
consulted_at  timestamptz
```

### search_keyword — 추천·자동완성 검색어
IA: BO 검색관리 › 부가서비스관리 › 추천검색어관리·자동완성어관리 · FO 검색 인풋 레이어 › 인기검색어

```
id            bigserial     PK
keyword_type  text          RECOMMENDED / AUTOCOMPLETE
keyword       text
sort_order    integer
start_at      timestamptz?
end_at        timestamptz?
use_yn        boolean
```

### search_log — 검색 로그
IA: FO 검색 › 최근검색어 · BO 검색관리 › 검색실패 관리 (result_count = 0)

```
id            bigserial    PK
member_id     bigint?      → member
keyword       text
result_count  integer
searched_at   timestamptz
```

### search_dictionary — 검색 사전
IA: BO 검색관리 › 사전관리

```
id           bigserial  PK
dict_type    text       SYNONYM / TYPO / STOPWORD
term         text
mapped_term  text?
```

### banned_word — 금지어
IA: BO 시스템관리 › 부가서비스 › 금지어관리

```
id      bigserial  PK
word    text       UQ
use_yn  boolean
```

## 9. BO 시스템 (system)

### bo_user — BO 사용자
IA: BO 시스템관리 › 사용자관리 › 사용자관리·계정연장요청관리

```
id                      bigserial     PK
login_id                text          UQ
password_hash           text
name                    text
email                   text
status                  text          ACTIVE / LOCKED / EXPIRED
account_expires_at      date
extension_requested_at  timestamptz?
```

### bo_role — 역할
IA: BO 시스템관리 › 권한관리 › 역할관리

```
id           bigserial  PK
code         text       UQ
name         text
description  text?
```

### bo_user_role — 사용자·역할

```
bo_user_id  bigint  → bo_user
bo_role_id  bigint  → bo_role
PK (bo_user_id, bo_role_id)
```

### bo_menu — BO 메뉴
IA: BO 시스템관리 › 권한관리 › 메뉴관리 (URL 검색·메뉴얼작성). 이 IA 문서의 BO 시트가 초기 데이터다.

```
id          bigserial  PK
parent_id   bigint?    → bo_menu
name        text
url         text?
depth       smallint
sort_order  integer
manual      text?      메뉴얼
use_yn      boolean
```

### bo_role_menu — 역할·메뉴

```
bo_role_id  bigint  → bo_role
bo_menu_id  bigint  → bo_menu
PK (bo_role_id, bo_menu_id)
```

### bo_url_group — URL 그룹
IA: BO 시스템관리 › 권한관리 › URL 그룹관리

```
id    bigserial  PK
code  text       UQ
name  text
```

### bo_url — URL 마스터
IA: BO 시스템관리 › 권한관리 › URL 마스터 관리

```
id               bigserial  PK
bo_url_group_id  bigint     → bo_url_group
url_pattern      text       UQ
method           text?
name             text
```

### bo_role_url_group — 역할·URL 그룹

```
bo_role_id       bigint  → bo_role
bo_url_group_id  bigint  → bo_url_group
PK (bo_role_id, bo_url_group_id)
```

### common_code — 공통코드
IA: BO 시스템관리 › 권한관리 › 공통코드관리. 이 문서의 `status` / `*_type` 후보 값이 여기 들어간다.

```
id          bigserial  PK
group_code  text
code        text
name        text
sort_order  integer
use_yn      boolean
UQ (group_code, code)
```

### holiday — 공휴일
IA: BO 시스템관리 › 공휴일관리. 배송 약속일·배송지연 계산에 쓴다.

```
id            bigserial  PK
holiday_date  date       UQ
name          text
```

### short_url — 단축 URL
IA: BO 시스템관리 › 부가서비스 › 단축URL

```
id          bigserial  PK
code        text       UQ
target_url  text
created_by  bigint     → bo_user
```
