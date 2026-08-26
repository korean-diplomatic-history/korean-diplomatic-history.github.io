# 한국외교사연구회

2006년부터 이어 온 한국외교사연구회의 모임 기록과 자료를 모은 아카이브입니다.
18세기 지성사 독회에서 연행록연구회를 거쳐 지금에 이르기까지, 회차별로 그날 읽은 글과
발제자, 남아 있는 토론 기록을 실었습니다.

## 만드는 법

```bash
python _build/assemble.py   # _harvest/ 원자료 → data/*.json
python build.py             # data/*.json → HTML
python build.py --serve     # 빌드 후 http://localhost:8000
python _build/digest.py     # 아카이브_정리.md · 아카이브_점검.md
```

`data/` 와 `templates/`, `assets/` 가 바뀌면 GitHub Actions 가 다시 빌드해 산출물을 커밋합니다.
저장소 루트의 `*.html` 은 **빌드 산출물이므로 직접 고치지 마십시오.**
자세한 규약은 [CLAUDE.md](CLAUDE.md) 에 있습니다.

## 게재 원칙

연구회 구성원이 모임을 위해 직접 쓴 발제문·요약문·발표자료는 본문을 싣습니다.
저작권이 살아 있는 단행본과 학술논문은 서지사항만 적고, 원문이 공개된 것은 그 링크로 연결합니다.
게재된 글의 권리는 각 작성자에게 있습니다. 게재를 원하지 않으시면 알려 주십시오.
