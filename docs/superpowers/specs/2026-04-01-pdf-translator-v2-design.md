# PDF Translator v2 — 설계 문서

> 작성일: 2026-04-01
> 상태: 승인됨

## 1. 개요

PDF 문서를 추출하고 병렬 번역하여 원본 레이아웃을 보존한 PDF와 Markdown을 생성하는 도구를 확장한다. CLI 도구에서 전문 번역 플랫폼으로 발전시킨다.

### 1.1 대상 사용자 (우선순위)

1. **연구자/학생** — 논문 번역, 수식/참고문헌/학술 용어 정확도
2. **기업/실무자** — 기술 문서, 매뉴얼, 보고서. 일관된 용어, 대량 처리
3. **일반 사용자** — 다양한 PDF 번역. 쉬운 접근성
4. **개발자** — 파이프라인 임베드. API 안정성

### 1.2 설계 원칙

- **CLI = 무료 우선**: API 키 없이 CLI 백엔드(Codex/Claude/Gemini)로 사용 가능
- **Backend = Protocol**: 새 백엔드 추가는 파일 1개
- **pip install 단계별**: 기본(CLI) / [ocr] / [web] / [all]
- **레이아웃 = 최우선**: 원본 PDF의 폰트/색상/구조를 최대한 보존

## 2. 아키텍처

### 2.1 코어 + 레이어 분리

```
pdf_translator/
├── core/                    # 순수 라이브러리 (비즈니스 로직)
│   ├── extractor.py         # PDF 텍스트 추출
│   ├── ocr/                 # OCR 파이프라인
│   │   ├── base.py          # OCREngine Protocol
│   │   ├── surya.py         # Surya 엔진 (기본)
│   │   └── tesseract.py     # Tesseract 엔진 (폴백)
│   ├── translator/          # 번역 엔진
│   │   ├── base.py          # TranslationBackend Protocol
│   │   ├── router.py        # 백엔드 자동 선택
│   │   ├── backends/        # 백엔드 구현체
│   │   │   ├── codex_cli.py
│   │   │   ├── claude_cli.py
│   │   │   ├── gemini_cli.py
│   │   │   ├── openai_api.py
│   │   │   ├── anthropic_api.py
│   │   │   ├── google_api.py
│   │   │   ├── openrouter_api.py
│   │   │   └── google_translate.py  # 무료 폴백
│   │   └── glossary.py      # 용어집 주입
│   ├── chunker.py           # 배치 빌더
│   ├── cache.py             # SQLite 번역 캐시
│   ├── glossary.py          # 용어집 관리 (3단 구조)
│   ├── draft.py             # Draft JSON 관리
│   ├── pdf_builder.py       # PDF 빌드 v2 (redaction + htmlbox)
│   ├── md_builder.py        # Markdown 빌드
│   └── config.py            # TranslatorConfig
├── cli/                     # CLI 진입점 (thin wrapper)
│   └── main.py
├── web/                     # 웹 애플리케이션
│   ├── api/                 # FastAPI REST + WebSocket
│   ├── frontend/            # React + TypeScript SPA
│   └── models.py            # DB 모델
└── pyproject.toml           # optional deps: [ocr], [web], [all]
```

### 2.2 데이터 흐름

```
PDF ──→ Extractor ──→ Elements[] ──→ Chunker ──→ Batches[]
  │      (+ OCR)        │                          │
  │                     │              ┌───────────┘
  │                     │              ▼
  │                     │         Translator
  │                     │          ├── Cache hit? → skip
  │                     │          ├── Glossary inject → prompt
  │                     │          └── Backend.translate()
  │                     │              │
  │                     │              ▼
  │                     │         Draft (JSON) ←── Review Mode
  │                     │              │               ↕
  │                     ▼              ▼          Web UI Edit
  │                Elements[] + Translations{}
  │                     │              │
  │                     ▼              ▼
  └──────────→ PDF Builder v2    MD Builder
               (redact+overlay)  (GFM output)
```

### 2.3 설치 옵션

| 명령 | 포함 기능 |
|------|-----------|
| `pip install pdf-translator` | CLI + Google Translate 폴백 |
| `pip install pdf-translator[ocr]` | + Surya + Tesseract |
| `pip install pdf-translator[web]` | + FastAPI + React SPA |
| `pip install pdf-translator[all]` | 전체 |

## 3. 레이아웃 보존 개선

### 3.1 현재 문제점

1. 흰 사각형이 테이블 경계선/배경 그래픽을 덮음
2. 원본 `font`, `font_size`, `text_color`를 추출하지만 사용하지 않음
3. `_fit_fontsize`가 글리프 폭이 아닌 0.6/1.0 휴리스틱 사용
4. `insert_textbox` 실패 시 `insert_text` 폴백이 줄바꿈 없음
5. 2단 레이아웃, 테이블 셀 인식 없음

### 3.2 개선 방안

**Step 1: Redaction으로 텍스트 제거**

```python
# Text PDF: 텍스트 레이어만 삭제, 벡터/이미지 보존
for rect in element_rects:
    page.add_redact_annot(rect, fill=(1, 1, 1))
page.apply_redactions(images=0, graphics=0)
```

**Step 2: 정확한 폰트 측정**

```python
font = fitz.Font("cjk")
width = font.text_length(text, fontsize=el.font_size)
```

`fitz.Font.text_length()`로 글리프 기반 정확한 측정. 현재 binary search 휴리스틱 대체.

**Step 3: CSS 스타일링 삽입**

```python
html = f'<span style="font-size:{fs}px; color:rgb({r},{g},{b})">{text}</span>'
page.insert_htmlbox(rect, html, scale_low=0)
```

원본 `font_size`, `text_color`, 정렬을 CSS로 반영. 자동 줄바꿈 + 축소.

**Step 4: 2단 레이아웃 감지**

Elements의 bbox x좌표를 클러스터링하여 컬럼 자동 감지. 읽기 순서 보존.

**Step 5: 텍스트 확장 처리**

1. fontsize 축소 (최소 4pt)
2. `insert_htmlbox` `scale_low=0` 자동 축소
3. 그래도 넘치면 ellipsis + Markdown에 풀텍스트

### 3.3 OCR 문서의 레이아웃 처리

스캔 PDF는 텍스트 레이어가 없으므로 redaction 대신 배경색 감지 후 덮기:

```python
# 1. 배경색 샘플링
pixmap = page.get_pixmap(clip=rect)
bg_color = _sample_background_color(pixmap)

# 2. 배경색으로 원본 이미지 글자 덮기
shape = page.new_shape()
shape.draw_rect(rect)
shape.finish(fill=bg_color)  # 흰색이 아닌 실제 배경색
shape.commit()

# 3. 번역 텍스트 삽입 (동일)
page.insert_htmlbox(rect, html, scale_low=0)
```

투명이나 흰색이 아닌 **실제 배경색**을 사용하여 원본 글자와 겹치는 문제를 방지한다.

## 4. LLM 백엔드 시스템

### 4.1 TranslationBackend Protocol

```python
@runtime_checkable
class TranslationBackend(Protocol):
    name: str                    # "codex", "claude-cli" 등
    backend_type: str            # "cli" | "api"

    def is_available(self) -> bool:
        """사용 가능 여부 (CLI 설치? API 키 존재?)"""
        ...

    def translate(
        self,
        texts: list[str],
        source_lang: str,
        target_lang: str,
        glossary: dict[str, str] | None = None,
    ) -> list[str | None]:
        """텍스트 리스트 번역. 실패 시 None"""
        ...
```

### 4.2 백엔드 목록

| 백엔드 | 타입 | 비용 | 비고 |
|--------|------|------|------|
| Codex CLI | cli | 무료 | 기존 지원 |
| Claude CLI | cli | 무료 | `claude --print` |
| Gemini CLI | cli | 무료 | `gemini` |
| OpenAI API | api | 유료 | GPT-4o 등 |
| Anthropic API | api | 유료 | Claude 모델 |
| Google API | api | 유료 | Gemini 모델 |
| OpenRouter | api | 유료 | 수백 개 모델 프록시 |
| Google Translate | api | 무료 | 최종 폴백 |

### 4.3 백엔드 자동 선택 (Router)

```
--backend auto (기본값):
  CLI 순회: codex → claude → gemini
    → 사용 가능한 것 발견 시 사용
    → 없으면 API 순회: openrouter → openai → anthropic → google
      → API 키 있는 것 발견 시 사용
      → 없으면 Google Translate (무료 폴백)

--backend claude-cli (명시적):
  → 사용 불가 시 에러 (폴백 없음)
```

### 4.4 프롬프트 전달 방식

모든 CLI 백엔드는 `subprocess.Popen` + `stdin`으로 프롬프트 전달. ARG_MAX 초과 및 `ps` 노출 방지.

## 5. 용어집 시스템

### 5.1 3단 구조

```
우선순위: 사용자 용어집 > 내장 팩 > 기본 규칙

1) 내장 용어집 (Built-in Packs)
   ├── cs-general.csv       # API, GPU, SDK → keep
   ├── ml-ai.csv            # transformer, BERT → keep
   ├── medical.csv
   └── legal.csv
   → 커뮤니티 기여로 확장 (GitHub PR)

2) keep-as-is 규칙
   source,target,rule
   API,API,keep              # 번역하지 않음
   BERT,BERT,keep

3) 사용자 용어집 (프로젝트별)
   source,target
   transformer,트랜스포머     # 내장 팩 오버라이드 가능
```

### 5.2 과번역/과소번역 방지

| 유형 | 예시 | 방지 방법 |
|------|------|-----------|
| 과번역 | API → 응용 프로그래밍 인터페이스 | keep-as-is 규칙 |
| 과소번역 | method → method (미번역) | translate 규칙 |

### 5.3 LLM 프롬프트 주입

```
GLOSSARY RULES:
- Keep these terms as-is (DO NOT translate): API, GPU, BERT, fine-tuning
- Use these translations: method → 방법, performance → 성능
- User glossary: transformer → 트랜스포머
```

### 5.4 비LLM 백엔드 (Google Translate)

후처리 치환: 번역 결과에서 용어집의 source가 잘못 번역된 경우 target으로 강제 치환.

### 5.5 용어집 포맷

- **CSV** (기본): 2컬럼 (`source,target`) 또는 3컬럼 (`source,target,rule`)
- **JSON** (고급): context 필드 포함 가능

## 6. OCR 파이프라인

### 6.1 자동 감지

```
PDF → 텍스트 추출 시도
  ├── 텍스트 충분 (>50자/페이지) → Text PDF 경로
  └── 텍스트 부족 → Scanned PDF → OCR 경로
```

### 6.2 엔진

| 엔진 | 역할 | 특징 |
|------|------|------|
| **Surya** | 기본 | ML 기반, 레이아웃 감지 내장, 90+ 언어, GPU 가속 |
| **Tesseract** | 폴백 | 경량, CPU 전용, 광범위 언어 지원 |

Surya 사용 조건: `pip install pdf-translator[ocr]` 시 설치됨.

Tesseract 폴백 조건: Surya 미설치, GPU 없는 환경, `--ocr-engine tesseract` 명시적 선택.

### 6.3 OCREngine Protocol

```python
class OCREngine(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def extract(
        self,
        page_image: bytes,
        lang: str,
    ) -> list[OCRResult]: ...
```

`OCRResult`는 `text`, `bbox`, `confidence` 필드를 포함한다.

## 7. Draft (리뷰) 시스템

### 7.1 Draft JSON 포맷

```json
{
  "source_file": "paper.pdf",
  "source_lang": "en",
  "target_lang": "ko",
  "backend": "claude-cli",
  "created_at": "2026-04-01T12:00:00Z",
  "elements": [
    {
      "index": 0,
      "type": "heading",
      "original": "Introduction",
      "translated": "소개",
      "status": "accepted",
      "confidence": 0.95,
      "page": 1,
      "bbox": [72, 90, 200, 110]
    }
  ],
  "glossary_applied": ["cs-general", "user-custom"]
}
```

`status` 값: `accepted` | `modified` | `rejected` | `pending`

### 7.2 CLI 명령

```bash
pdf-translator paper.pdf --draft-only              # Draft만 저장
pdf-translator --build-from draft.json             # Draft에서 PDF 빌드
pdf-translator --retranslate draft.json --backend openai-api  # 미승인 항목 재번역
```

### 7.3 웹 UI 연동

웹 UI에서 Draft를 실시간 편집 → WebSocket으로 변경사항 반영 → PDF/MD 내보내기.

## 8. 웹 UI

### 8.1 기술 스택

| 레이어 | 기술 | 역할 |
|--------|------|------|
| Backend | FastAPI | REST API + WebSocket |
| DB | SQLite | 프로젝트/용어집/캐시 |
| 실시간 | WebSocket | 번역 진행률 푸시 |
| 비동기 | Background Tasks | 번역 작업 실행 |
| Frontend | React + TypeScript | SPA |
| 스타일 | TailwindCSS | UI 스타일링 |
| PDF 뷰어 | PDF.js | 원본 PDF 렌더링 |
| 비교 | react-diff-viewer | 변경사항 비교 |

### 8.2 주요 화면

**메인 번역 화면 (Side-by-Side)**
- 왼쪽: 원본 PDF 뷰어 (PDF.js). 용어 하이라이트, 클릭하면 용어집 등록
- 오른쪽: 번역 결과. 호버하면 편집 가능, 상태 표시 (승인/수정/대기)
- 동기 스크롤: 원본과 번역이 같은 위치에서 맞춤

**하단 도구 패널**
- 용어집: 원문↔번역↔규칙 테이블, 실시간 편집, CSV 임포트/엑스포트
- 번역 상태: 승인/수정/대기/실패 카운트 + 진행률 바
- 내보내기: PDF/MD 버튼

### 8.3 API 엔드포인트 (주요)

```
POST   /api/projects              # 프로젝트 생성 (PDF 업로드)
GET    /api/projects/:id          # 프로젝트 조회
POST   /api/projects/:id/translate  # 번역 시작
WS     /api/projects/:id/ws       # 실시간 진행률
GET    /api/projects/:id/draft    # Draft 조회
PATCH  /api/projects/:id/draft/:idx  # 세그먼트 수정
POST   /api/projects/:id/export/pdf  # PDF 내보내기
POST   /api/projects/:id/export/md   # MD 내보내기
GET    /api/glossaries            # 용어집 목록
POST   /api/glossaries            # 용어집 생성
PUT    /api/glossaries/:id        # 용어집 수정
POST   /api/glossaries/import     # CSV 임포트
```

## 9. Python 라이브러리 API

코어 리팩토링의 결과로 자연스럽게 제공되는 프로그래밍 인터페이스.

### 9.1 기본 사용

```python
from pdf_translator.core import translate_pdf, TranslateOptions

result = translate_pdf(
    "paper.pdf",
    target_lang="ko",
    backend="auto",            # 자동 선택 (기본값)
    glossary="terms.csv",      # 용어집 (선택)
)

result.save_pdf("output.pdf")
result.save_markdown("output.md")
result.save_draft("draft.json")
```

### 9.2 세부 제어

```python
from pdf_translator.core.extractor import extract_pdf
from pdf_translator.core.translator import create_backend
from pdf_translator.core.pdf_builder import build_pdf

# 단계별 실행
elements = extract_pdf("paper.pdf")
backend = create_backend("claude-cli")
translations = backend.translate(
    [el.content for el in elements],
    source_lang="en", target_lang="ko",
)
build_pdf("paper.pdf", "output.pdf", elements, translations)
```

### 9.3 Draft 조작

```python
from pdf_translator.core.draft import Draft

draft = Draft.load("draft.json")
draft.elements[3].user_edit = "수정된 번역"
draft.elements[3].status = "modified"
draft.save("draft.json")
draft.build_pdf("output.pdf")
```

## 10. 구현 페이즈

### Phase 1: 기반 (Foundation)

| 태스크 | 내용 | 의존성 |
|--------|------|--------|
| 1a | 코어 리팩토링 — `core/` 패키지 분리, Python API | 없음 |
| 1b | 레이아웃 개선 — pdf_builder v2 (redaction + insert_htmlbox) | 1a |
| 1c | 백엔드 플러그인 — Protocol + codex/claude-cli/gemini-cli + auto router | 1a |

Phase 1 완료 시: 레이아웃 대폭 개선된 CLI + 3개 CLI 백엔드.

### Phase 2: 핵심 기능 (Core Features)

| 태스크 | 내용 | 의존성 |
|--------|------|--------|
| 2a | 용어집 시스템 — 3단 구조 + 내장 팩 | 1c |
| 2b | Draft 시스템 — JSON draft + CLI 명령 | 1a |
| 2c | API 백엔드 — OpenAI, Anthropic, Google, OpenRouter | 1c |

Phase 2 완료 시: 전문 번역 도구로서 기능 완성.

### Phase 3: OCR 확장 (병렬 가능)

| 태스크 | 내용 | 의존성 |
|--------|------|--------|
| 3a | Surya 통합 — 레이아웃 감지 + OCR | 1a |
| 3b | Tesseract 폴백 | 3a |
| 3c | OCR 빌더 로직 — 배경색 샘플링 + 덮기 | 1b |
| 3d | 자동 감지 — Text PDF vs Scanned PDF 판별 | 3a |

Phase 3 완료 시: 스캔 문서 번역 가능.

### Phase 4: 웹 UI

| 태스크 | 내용 | 의존성 |
|--------|------|--------|
| 4a | FastAPI 서버 — REST API + WebSocket | 2b |
| 4b | React SPA — Side-by-side 뷰어 | 4a |
| 4c | 인라인 편집 — Draft 실시간 수정 | 4a, 4b |
| 4d | 용어집 UI — 드래그 등록, 관리 패널 | 2a, 4b |
| 4e | PDF.js 원본 뷰어 | 4b |

Phase 4 완료 시: 비개발자도 쓸 수 있는 풀 웹 인터페이스.

### 의존 관계 요약

```
Phase 1 ──→ Phase 2 ──→ Phase 4
   │
   └──────→ Phase 3 (독립적, Phase 2와 병렬 가능)
```
