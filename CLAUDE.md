# 한국외교사연구회 — 웹사이트

한국외교사연구회(한외사)의 20년치 모임 기록을 GitHub Pages 로 발행하는 작업 폴더.
디자인 참조는 `https://complex-intelligence.github.io/` 와 `Projects/circle-of-fish`
(같은 레이아웃 DNA, 남빛·단청 팔레트).

## 구조

```
_harvest/      ← 원자료. **저장소에 올리지 않는다**(.gitignore). 세 소스의 수확물이 여기 쌓인다
data/          ← 콘텐츠 정본(JSON). _build/assemble.py 가 _harvest 에서 만들어 낸다
templates/     ← Jinja2 (base + 페이지 7종 + 회차 상세 + _timeline 매크로)
assets/        ← style.css, favicon.svg → 빌드 시 루트로 복사
files/         ← **공개로 판정된 자료 파일만.** assemble.py 가 동기화한다(손대지 말 것)
_build/        ← assemble.py — _harvest → data 조립기
build.py       ← 정적 사이트 생성기
.github/workflows/build.yml
               ← data·templates·assets 가 바뀌면 재빌드해서 HTML 을 커밋한다
*.html · sessions/ · style.css …
               ← **빌드 산출물. 직접 고치지 말 것.** 저장소 루트에서 그대로 발행된다
```

빌드·미리보기:

```bash
python _build/assemble.py             # _harvest → data/*.json 재조립
python build.py                       # data → HTML
python build.py --serve --port 8000   # 빌드 후 http://localhost:8000
```

산출물이 소스와 같은 폴더에 놓이므로, 빌드는 **자기가 만든 파일만** 지운다
(`generated_paths()`). `files/` 는 거기 없으므로 지워지지 않는다.

## 페이지 구성

- `index.html` 처음
- `sessions.html` **모임 기록** — 2020년 3월부터. 부제 「지구사로서 한국외교사」
- `archive.html` **지난 기록** — 그 이전. 18세기 지성사 독회·연행록연구회·한국외교사연구회 초기
- `materials.html` **자료** — 날짜순이 아니라 **주제별**. 목차는 `_harvest/themes.json` 이 정한다
- `members.html` **참여 연구자** — 2024년 이후 참여자와 「함께했던 분들」 두 절
- `about.html` 연구회 소개
- `sessions/<날짜>.html` 회차 상세

경계는 `_build/assemble.py` 의 `SPLIT`(2020-03-01)·`ACTIVE`(2024-01-01) 두 상수다.

### 회차 정보는 세 갈래로 통일한다

연표·회차 상세 어디서나 같은 차례다. 뼈대는 `_material.html.j2` 의 `body()` 매크로 하나뿐이라,
고칠 일이 있으면 거기만 고치면 세 쪽이 함께 바뀐다.

1. **독회 문헌** — 그날 읽은 텍스트의 서지. 그 텍스트의 파일이 있으면 서지 밑에 붙는다.
2. **발제자 및 발제자료** — 발제자와 그가 맡은 대목, 그 밑에 그 사람의 발제문.
3. **기타 자료** — 그 밖에 돌려 본 것.

**파일명을 화면에 내보내지 않는다.** 자료는 `title`(사람이 읽을 제목)로 보이고 링크가 파일을 문다.
`title`·`group`·`presenter` 는 `_harvest/material_titles.json` 이 정하며, 없으면 파일명으로 떨어진다.
"자료 3" 같은 개수 표기도 쓰지 않는다.

## 세 소스

| 소스 | 기간 | 무엇 | 수확물 |
|---|---|---|---|
| 하영선 홈페이지 `hayoungsun.net/meet1.asp` | 2006–2021 | 회차 74건 + 토론 기록 본문 + 첨부 PDF 149건 | `_harvest/hayoungsun/` |
| 지메일 (`한국외교사연구회 OR 한외사`) | 2018–2026 | 스레드 151건 — 공지·발제 배분·발제문 회람 | `_harvest/gmail/extract.json` |
| 구글드라이브 `하샘 외교사모임` | 2021–2025 | 파일 47건 | `_harvest/drive/files.json` |

회차는 **날짜(YYYY-MM-DD)를 키로 합친다.** 하영선 홈페이지의 게시 날짜는 개최일과
다를 수 있어(2021년 3·4·5월, 2015년 10월), 기록 본문의 "일시:" 를 정본으로 쓴다
(`_harvest/records_extract.json`).

## 저작권 원칙 (사이트의 존재 조건)

- **공개(public)** — 연구회 구성원이 그 모임을 위해 직접 쓴 글: 발제문·요약문·토론 기록·발표자료.
  파일을 `files/` 에 올리고 본문을 링크한다.
- **외부 링크(external)** — 저작권자가 전문을 무료 공개한 것(KCI 무료공개, 오픈액세스,
  공공기관 간행물, 저작권 소멸한 원 사료). **링크만** 걸고 파일은 올리지 않는다.
- **비공개(restricted)** — 상업 출판 단행본·번역서 스캔, 오픈액세스가 아닌 학술논문,
  남의 미출판 원고. 서지사항만 표기한다.

판정 결과는 `_harvest/classify.json` 이 정본이고, `assemble.py` 가 이를 읽어
`data/materials.json` 의 `access` 를 정한다. **판정 파일이 없거나 항목이 빠지면
기본값은 restricted 다** — 공개 쪽으로 기울지 않게 일부러 그렇게 두었다.

## 파생 데이터 (모두 `_harvest/` 안)

| 파일 | 무엇 | 만든 방법 |
|---|---|---|
| `records_extract.json` | 옛 기록 74건의 실제 개최일·발제자·읽은 글 | 워크플로 |
| `classify.json` | 자료 261건의 성격·공개 가부·공개 원문 링크 | 워크플로 |
| `themes.json` | 주제 체계와 회차·자료 배정, 손본 주제문 | 워크플로 |
| `readings_clean.json` | 읽은 글 164건의 정돈된 서지 | 워크플로 |
| `material_titles.json` | 자료의 표시 제목·발제자 귀속·세 갈래 분류 | 워크플로 |
| `gmail/attachments_saved.json` | 지메일 원문에서 꺼낸 첨부 목록 | 워크플로 |
| `overrides.json` | 손으로 고치는 것 — `alias`·`active`·`alumni`·`affil` | 사람 |

`overrides.json` 은 조립기가 마지막에 얹는다. 이름 이형(`chaeyoung yong` → `용채영`),
현역/알럼나이 강제 지정, 소속을 여기에 적는다.

## 함정

- **`<책명>` 표기를 HTML 태그로 지우지 말 것.** 하영선 홈페이지 본문은 서명을 `<...>` 로
  쓴다. 태그 제거 정규식은 `</?[A-Za-z]...>` 형태만 지워야 한다. 한 번 이것 때문에
  2,796개 서명이 통째로 날아가 기록 추출을 다시 돌렸다.
- **지메일 첨부는 `get_message` 의 `RAW` 로 꺼낸다.** 전용 다운로드 도구는 없지만 RAW 가
  base64 MIME 을 통째로 준다 — 로컬에서 `email` 모듈로 풀면 첨부가 그대로 나온다.
  결과가 커서 파일로 떨어지면 그 경로가 곧 데이터다. 꺼낸 것은 `_harvest/gmail/files/` 에 둔다.
  파일 이름은 NFC 로 정규화하고 `\/:*?"<>|` 를 `_` 로 바꿔 저장한다(`safe_name()`).
- 지메일·드라이브에서 뽑은 텍스트는 모델이 `&lt;` 로 이스케이프해 돌려준다 —
  `html.unescape` 를 반드시 거칠 것.
- Jinja2 는 `StrictUndefined` 다. 레코드마다 있을 수도 없을 수도 있는 필드는
  `x.get('field')` 로 접근해야 한다.
- 산출물 HTML 을 직접 고치면 다음 빌드에 날아간다. 고칠 것은 `data/` 나 `_harvest/` 에.
- **홈페이지 문구에 아카이브 작업 과정을 쓰지 말 것.** "기록에서 뽑은 것이라 빠진 분이 있을 수
  있습니다" 류의 자기 해명은 연구 모임 홈페이지가 하는 말이 아니다. 한 번 지웠다.
- `readings_clean.json` 의 `rid` 는 `<회차>#<순번>` 이라 **읽은 글 순서에 매여 있다.**
  조립기가 `readings_input.json` 의 `raw` 와 대조해 어긋나면 조용히 건너뛴다 —
  `add_reading` 로직을 고쳤으면 `readings_input.json` 을 다시 뽑고 워크플로를 다시 돌려야 한다.
- **참여 여부는 발제 기록만으로 판정하면 안 된다.** 2022년 이후 기록이 메일뿐이라
  좌장(하영선)조차 알럼나이로 밀린다. 회람 메일의 `participants` 를 최근성 근거로 함께 쓴다.
