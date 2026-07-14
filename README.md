# 에이블런 GPT 계정 자동화 (GPT_automation)

교육생에게 배정하는 `gpt1@ablearn.kr` ~ `gpt30@ablearn.kr` 계정의 **① 초기화(로그아웃/데이터 삭제)** 와 **② Google Groups 멤버 등록**을 자동화하는 사내 도구 모음입니다.

> **바쁘면 여기만 읽으세요:** 대부분의 사용자는 `gpt_manager/` 안의 GUI 앱 하나만 있으면 됩니다. 개발자용 CLI 스크립트나 Chrome 확장 프로그램은 특수한 상황에서만 필요합니다. → [빠른 시작](#빠른-시작-일반-사용자)

---

## 목차

1. [이 폴더에 포함된 도구들](#이-폴더에-포함된-도구들)
2. [빠른 시작 (일반 사용자)](#빠른-시작-일반-사용자)
3. [인증 정보 설정 방법 (API 키 없음 · 대신 이 3가지가 필요)](#인증-정보-설정-방법)
4. [개발자용: 소스코드로 직접 실행하기](#개발자용-소스코드로-직접-실행하기)
5. [gpt_manager 앱 상세 사용법](#gpt_manager-앱-상세-사용법)
6. [배포용 실행 파일 빌드 방법](#배포용-실행-파일-빌드-방법)
7. [CLI 스크립트 상세 사용법](#cli-스크립트-상세-사용법)
8. [기타 스크립트 (참고용)](#기타-스크립트-참고용)
9. [폴더 구조](#폴더-구조)
10. [배포 시 반드시 확인할 것 (보안)](#배포-시-반드시-확인할-것-보안)
11. [문제 해결](#문제-해결)
12. [문의](#문의)

---

## 이 폴더에 포함된 도구들

| 도구 | 용도 | 대상 사용자 | 비고 |
|---|---|---|---|
| **`gpt_manager/`** | 계정 초기화 + 멤버 추가를 하나의 화면(GUI)에서 처리 | **일반 사용자 (추천)** | 실행 파일로 빌드해서 배포 가능 |
| **`chrome_extension/`** | 멤버 추가 전용 Chrome 확장 프로그램 | 브라우저만으로 간단히 처리하고 싶은 사용자 | 자체 [README](chrome_extension/README.md)에 설치·배포 방법이 이미 잘 정리되어 있음 |
| `reset_gpt_accounts.py`, `reset_gpt_accounts_parallel.py` | 계정 초기화 (터미널 CLI) | 개발자 / 터미널 사용 가능자 | `gpt_manager`의 원본 로직 |
| `add_members.py` | 멤버 추가 (터미널 CLI) | 개발자 / 터미널 사용 가능자 | `gpt_manager`의 원본 로직 |
| `crawl_agency_emails.py` | **별개 기능** — 수행기관 홈페이지에서 이메일 주소 수집 | 해당 업무 담당자 | 계정 초기화/멤버 추가와 무관 |
| `fix_indent.py` | 코드 들여쓰기를 고치는 1회성 개발 유틸 | 개발자 | 일반 사용자는 무시 |
| `tt.py` | 용도 불명확 · 현재 상태로는 실행 불가 | - | [기타 스크립트](#기타-스크립트-참고용) 참고 |

---

## 빠른 시작 (일반 사용자)

`gpt_manager` 앱을 쓰는 경우, 아래 4단계면 끝입니다.

1. 담당자(문의처: [국필호(피터), peter@ablearn.kr](#문의))에게 배포된 실행 파일(`GPT_Manager.exe` 또는 `GPT_Manager` 앱)을 받아 더블 클릭으로 실행합니다. 자동으로 브라우저가 열리며 `http://localhost:8080` 화면이 뜹니다.
2. **설정** 탭에서 마스터 이메일 / 앱 비밀번호 / 공통 비밀번호를 입력하고 저장합니다. → 값을 어디서 구하는지는 [인증 정보 설정 방법](#인증-정보-설정-방법) 참고.
3. **계정 초기화** 탭에서 처리할 계정 번호 범위(예: `1~10`)를 입력하고 "초기화 시작"을 누릅니다.
4. **멤버 추가** 탭에서는 엑셀에서 이메일/GPT계정 두 열을 복사해 표에 붙여넣고 "자동 추가 시작"을 누릅니다. (Google Workspace 관리자 계정으로 Chrome 로그인 필요 — 아래 참고)

실행 파일이 아직 없다면 [배포용 실행 파일 빌드 방법](#배포용-실행-파일-빌드-방법)을 참고해 직접 빌드하거나, 개발자에게 빌드를 요청하세요.

---

## 인증 정보 설정 방법

이 프로젝트는 OpenAI나 Google의 **유료 API 키를 사용하지 않습니다.** 대신 아래 값들만 있으면 됩니다. 처음 설정하는 사람은 아래 체크리스트 순서대로 진행하면 됩니다.

### ✅ 처음 설정하는 사람을 위한 체크리스트

- [ ] Google Chrome 브라우저 설치 (실제 Chrome이어야 함, Chromium/Edge 등 불가)
- [ ] **[초기화 기능]** 마스터 Gmail 계정이 무엇인지 확인 (현재: `peter@ablearn.kr`)
- [ ] **[초기화 기능]** 그 계정에 2단계 인증이 켜져 있는지 확인, 없으면 활성화
- [ ] **[초기화 기능]** 그 계정의 Gmail **앱 비밀번호** 발급
- [ ] **[초기화 기능]** gpt1~30 **공통 비밀번호** 담당자에게 문의해서 받기
- [ ] **[멤버 추가 기능]** `ablearn.kr` Google Workspace 관리자(최소 "그룹 관리자") 계정으로 Chrome 로그인
- [ ] 위 값을 `gpt_manager` 앱의 설정 탭 (또는 `.env`)에 입력

아래는 각 항목의 상세 설명과, **어디서/어떻게 발급받는지**입니다.

### 1. 마스터 이메일 (MASTER_EMAIL)

**이게 뭔가요?** gpt1~gpt30 각 계정으로 OpenAI(ChatGPT)가 보내는 로그인 인증 코드(6자리 숫자)를 한 곳에서 받기 위한 Gmail 주소입니다. 코드가 이 메일함에 IMAP(`imap.gmail.com`)으로 직접 접속해서 "전체보관함"을 뒤져 인증 코드를 자동으로 읽어옵니다 (`gpt_manager/utils/imap_helper.py` 기준).

**왜 30개 계정의 코드가 메일 한 곳에 다 모이나요?** `gptN@ablearn.kr` 앞으로 온 메일이 마스터 이메일로도 함께 전달되도록 이미 설정되어 있기 때문입니다 (코드가 메일의 `To` / `Delivered-To` / `X-Original-To` 헤더를 보고 어느 gptN 계정 앞으로 온 메일인지 구분합니다). **이 전달 규칙 자체는 이 저장소의 코드가 아니라 Google Workspace 관리자 콘솔([admin.google.com](https://admin.google.com)) 쪽 설정**입니다. 즉, 마스터 이메일을 바꾸거나 이 시스템을 처음부터 새로 구축하려면 Workspace 관리자 콘솔에서 "gptN@ablearn.kr → 마스터 이메일로 전달" 규칙(별칭 또는 라우팅)을 먼저 만들어야 합니다. 구체적인 절차는 이 저장소만으로는 확인할 수 없으니 현재 ablearn.kr Workspace를 관리하는 담당자에게 확인하세요.

**어떻게 구하나요?**
- 기존 시스템을 이어받는 경우 → 담당자([문의](#문의))에게 이 계정을 계속 써도 되는지 확인하고, [앱 비밀번호](#2-앱-비밀번호-app_password--gmail-앱-비밀번호)만 새로 발급받으면 됩니다.
- 완전히 새로운 마스터 계정으로 바꾸는 경우 → 위 전달 규칙을 새 계정 기준으로 Workspace 관리자 콘솔에서 다시 구성해야 합니다 (Workspace 관리자 권한 필요).

### 2. 앱 비밀번호 (APP_PASSWORD) — Gmail 앱 비밀번호

마스터 이메일 계정의 Gmail에 IMAP으로 접속해 인증 코드를 자동으로 읽어오기 위한 16자리 비밀번호입니다. 일반 로그인 비밀번호가 아니라 **Google의 "앱 비밀번호"** 기능으로 별도 발급해야 합니다. (아래 절차는 `gpt_manager` 앱의 설정 화면에도 그대로 안내되어 있고, 2026년 7월 기준 Google에서 여전히 제공하는 기능입니다.)

1. 마스터 이메일 계정으로 [Google 계정 보안 페이지](https://myaccount.google.com/security)에 로그인 → "2단계 인증"이 꺼져 있다면 먼저 켭니다. **앱 비밀번호는 2단계 인증이 켜져 있어야만 발급할 수 있습니다.**
2. [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) 접속 (또는: Google 계정 → 보안 → "Google에 로그인" 섹션 → "앱 비밀번호")
3. 앱 이름에 `GPT자동화` 등 알아보기 쉬운 이름을 입력하고 "만들기" 클릭
4. 화면에 표시되는 16자리 비밀번호를 복사 (⚠️ 이 창을 닫으면 같은 비밀번호를 다시 볼 수 없으니 반드시 복사)
5. 띄어쓰기 없이 앱의 "앱 비밀번호" 칸에 붙여넣기 (예: `abcdefghijklmnop`)

> **"앱 비밀번호" 메뉴 자체가 안 보인다면?** 회사 Google Workspace 관리자가 조직 전체에서 앱 비밀번호 생성을 막아뒀을 수 있습니다. Workspace 관리자 콘솔(admin.google.com) → 보안 → 인증 → 2단계 인증 → **"사용자가 앱 비밀번호를 생성하도록 허용"** 항목이 켜져 있어야 합니다. 이 설정은 Workspace 관리자만 바꿀 수 있으니, 안 보이면 관리자에게 이 설정 확인을 요청하세요.
>
> 참고로 Google은 일반적으로 앱 비밀번호보다 OAuth("Google로 로그인") 방식을 권장하지만, 이 프로젝트는 IMAP으로 메일함에 직접 접속해야 하는 구조라 앱 비밀번호가 필요합니다.

### 3. 공통 비밀번호 (COMMON_PASSWORD)

gpt1~gpt30 계정에 공통으로 걸려 있는 ChatGPT 로그인 비밀번호입니다. 어딘가에서 새로 발급받는 값이 아니라, gpt1~30 계정을 만들 때 이미 정해서 사용 중인 **사내 공유 비밀번호**입니다. 담당자([문의](#문의))에게 요청해서 전달받으세요.

### 4. Google Workspace 관리자 계정 (멤버 추가 기능 전용)

API 키나 비밀번호를 코드/설정 화면에 입력하는 방식이 아니라, **Chrome 브라우저 자체가 `ablearn.kr` 도메인의 Google Workspace 관리자 계정으로 로그인되어 있어야** 동작합니다. 일반 계정은 Google Groups 멤버 추가 권한이 없어 실패합니다.

- **필요한 최소 권한:** Workspace의 사전 정의된 관리자 역할 중 **"그룹 관리자(Groups Admin)"**면 충분합니다. 그룹 생성/삭제, 멤버 추가/삭제 등 Google Groups 관련 권한만 있는 역할이라 최고 관리자(Super Admin) 권한까지는 필요 없습니다.
- **내가 관리자인지 확인하는 방법:** [admin.google.com](https://admin.google.com)에 마스터 계정으로 접속해봅니다. 접속 자체가 안 되거나 그룹 관리 메뉴가 없다면 권한이 없는 것입니다.
- **권한이 없다면:** 현재 Workspace 최고 관리자(담당자, [문의](#문의) 참고)에게 본인 계정에 "그룹 관리자" 역할을 부여해달라고 요청하세요.

이 요구사항은 `add_members.py`, `gpt_manager`의 멤버 추가 기능, `chrome_extension` 모두 동일합니다.

### 값을 실제로 어디에 입력하나요?

같은 값이지만 도구에 따라 **저장 위치가 다릅니다.**

| 사용하는 도구 | 입력 위치 | 파일 |
|---|---|---|
| `gpt_manager` 앱 | 앱 안의 **설정** 탭 | `gpt_manager/config.json` (앱이 자동 생성) |
| `reset_gpt_accounts.py`, `reset_gpt_accounts_parallel.py` | `.env` 파일을 직접 만들어서 | `GPT_automation/.env` (`.env.example`을 복사해서 사용) |
| `add_members.py`, `chrome_extension` | 필요 없음 (실행 시 브라우저에서 직접 Google 로그인) | - |

```bash
# CLI 스크립트를 쓰는 경우에만 필요
cp .env.example .env
# .env 파일을 열어 MASTER_EMAIL / APP_PASSWORD / COMMON_PASSWORD 입력
```

> `gpt_manager/config.json`의 비밀번호는 base64로 인코딩되어 저장되지만, 이는 **암호화가 아니라 단순 난독화**입니다. 파일을 열면 누구나 원래 값으로 복원할 수 있으니 평문 비밀번호와 동일하게 취급하고 공유하지 마세요.

---

## 개발자용: 소스코드로 직접 실행하기

### 사전 준비물

- Python 3.x (저장소에 명시된 최소 버전은 없으나 3.10 이상 권장)
- **Google Chrome 브라우저**가 실제로 설치되어 있어야 함 (Playwright/Selenium이 시스템 Chrome을 직접 구동함 — Chromium 아님)

### 설치

```bash
# 저장소 루트(GPT_automation)에서
python -m venv venv
source venv/bin/activate        # Windows는 venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt`는 CLI 스크립트와 `gpt_manager`가 필요로 하는 패키지를 모두 포함합니다. `gpt_manager`만 실행/빌드할 경우 `gpt_manager/requirements.txt`만 설치해도 됩니다.

멤버 추가 관련 기능(`add_members.py`, `gpt_manager`의 멤버 추가, 초기 설정)을 쓴다면 Playwright 브라우저 설치가 한 번 더 필요할 수 있습니다 (코드 내 안내 메시지 기준):

```bash
pip3 install playwright && playwright install chromium
```

### ⚠️ requirements.txt에 빠져 있는 패키지

아래 스크립트들은 코드에서 직접 import하지만 `requirements.txt`에는 포함되어 있지 않은 패키지가 있습니다. 실행 전 별도로 설치해야 합니다.

- `crawl_agency_emails.py` → `httpx` 필요 (`pip install httpx`)
- `crawl_agency_emails.py`의 `.xls` 입력 파일 읽기 → `xlrd` 필요 (`pip install xlrd`)
- `tt.py` → `google-auth-oauthlib` 필요 (단, 이 스크립트는 [기타 스크립트](#기타-스크립트-참고용) 참고 — 사용을 권장하지 않습니다)

---

## gpt_manager 앱 상세 사용법

`gpt_manager`는 FastAPI로 만든 로컬 웹 서버 + 브라우저 UI입니다. 실행하면 PC 안에서만 동작하는 서버가 뜨고, 자동으로 기본 브라우저가 열려 `http://localhost:8080`에 접속합니다. 인터넷의 다른 사람이 접근할 수 있는 구조가 아닙니다.

```bash
cd gpt_manager
pip install -r requirements.txt
python app.py
```

화면은 좌측 사이드바에 3개 탭으로 구성되어 있습니다.

- **계정 초기화**: 처리할 계정 번호를 `1~10, 12, 15~17` 형식으로 입력 → 동시 처리 수(1개 또는 2개)를 선택 → "초기화 시작". 채팅 기록·라이브러리·프로젝트를 삭제하고 모든 기기에서 로그아웃까지 진행합니다. (서버 쪽에서 동시 처리 수는 아무리 높게 설정해도 **최대 2개로 강제 제한**됩니다.)
- **멤버 추가**: 엑셀/스프레드시트에서 "이메일" + "GPT 계정" 두 열을 복사해 표에 붙여넣고 "▶ 순차적 자동 추가 시작" 클릭. 자동으로 열리는 브라우저에서 **회사 계정(ablearn.kr)의 Workspace 관리자 계정**으로 Google 로그인 후 앱에서 "로그인 완료" 버튼을 눌러야 진행됩니다.
- **설정**: [인증 정보 설정 방법](#인증-정보-설정-방법)에서 설명한 3가지 값을 입력하는 화면입니다. Gmail 앱 비밀번호 발급 가이드가 화면 안에도 그대로 포함되어 있습니다.

---

## 배포용 실행 파일 빌드 방법

비개발자에게 배포할 때는 Python 설치 없이 더블 클릭만으로 실행되는 파일로 만들어서 전달합니다. PyInstaller를 사용합니다.

```bash
cd gpt_manager

# macOS
bash build_mac.sh

# Windows
build_win.bat

# 운영체제 상관없이 Python으로 직접 실행하고 싶다면
python build.py
```

- 빌드 결과물은 `gpt_manager/dist/GPT_Manager/` 폴더 안에 생성됩니다.
- macOS는 `dist/GPT_Manager/GPT_Manager`, Windows는 `dist\GPT_Manager\GPT_Manager.exe`를 더블 클릭하면 실행됩니다.
- 처음 빌드하는 PC에는 `pyinstaller`가 없으면 스크립트가 자동으로 설치를 시도합니다.
- **macOS에서 빌드한 실행 파일은 Windows에서 동작하지 않고, 그 반대도 마찬가지입니다.** 배포 대상 OS와 같은 OS에서 빌드해야 합니다.

---

## CLI 스크립트 상세 사용법

터미널 사용이 익숙한 개발자/파워유저를 위한 원본 스크립트입니다. `gpt_manager`가 내부적으로 이 로직들을 그대로 가져다 쓰고 있습니다.

### `reset_gpt_accounts.py` / `reset_gpt_accounts_parallel.py`

```bash
python reset_gpt_accounts.py            # 한 번에 계정 1개씩 순차 처리
python reset_gpt_accounts_parallel.py   # 최대 2개 계정 동시 처리 (ThreadPoolExecutor)
```

실행하면 처리할 계정 번호 범위를 물어봅니다 (예: `1~10, 12, 15~17`). `.env` 설정이 먼저 되어 있어야 합니다.

> **차이점:** `reset_gpt_accounts_parallel.py`는 설치된 Chrome 버전을 자동 감지합니다. 반면 `reset_gpt_accounts.py`는 `version_main=147`로 **버전이 코드에 고정**되어 있어, Chrome이 자동 업데이트되어 메이저 버전이 바뀌면 드라이버 버전 불일치로 실행이 실패할 수 있습니다. Chrome 버전 문제가 생기면 `reset_gpt_accounts_parallel.py` 사용을 권장합니다.

### `add_members.py`

```bash
python add_members.py
```

같은 폴더의 `list.xlsx` (A열: 등록할 이메일, B열: GPT 계정번호)를 읽어 Google Groups에 순차적으로 멤버를 추가합니다. 실행하면 브라우저가 열리고 수동으로 1회 Google 로그인을 해야 합니다 (Workspace 관리자 계정 필요).

---

## 기타 스크립트 (참고용)

계정 초기화·멤버 추가 기능과는 직접 관련이 없는, 이 폴더에 함께 들어있는 스크립트입니다.

### `crawl_agency_emails.py`

수행기관 홈페이지를 크롤링해 담당자 이메일을 수집하는 별도 목적의 스크립트입니다. 로그인이나 API 키가 필요 없습니다.

```bash
python crawl_agency_emails.py --input 수행기관조회_20260520.xls --output 결과.xlsx --limit 10 --delay 1.0
```

- `--limit`: 처리할 기관 수 (기본 10건)
- `--delay`: 요청 사이 대기 시간(초) — 상대 서버에 부담을 주지 않기 위한 값입니다.

### `fix_indent.py`

`reset_gpt_accounts_parallel.py`의 특정 줄 범위(207~456번째 줄)에 들여쓰기를 추가하기 위해 한 번 쓰고 버려진 개발용 유틸리티로 보입니다. 실행할수록 대상 파일에 들여쓰기가 누적되어 코드가 깨질 수 있으므로 **다시 실행하지 마세요.**

### `tt.py` — 용도 불명확, 실행 불가 상태

Gmail/Calendar/Drive에 대한 Google OAuth 인증을 수행하고 토큰을 `~/.hermes/token.json`에 저장하는 코드입니다. 그러나:

- 첫 줄이 `python`이라는 글자로 시작해 **그대로 실행하면 오류가 납니다** (터미널 명령어가 코드 첫 줄에 잘못 붙어있는 것으로 보입니다).
- `~/.hermes/...` 라는 경로나 "Hermes"라는 이름이 이 저장소의 다른 어떤 코드와도 연결되어 있지 않습니다.
- `google-auth-oauthlib` 패키지가 `requirements.txt`에 없고, `~/Downloads/client_secret.json`이라는 별도 파일이 있어야 동작하는데 이 파일의 출처도 이 저장소 안에는 없습니다.

이 파일이 실제로 왜 필요한지, 계속 써야 하는 코드인지는 이 저장소만으로는 확인할 수 없습니다. 담당자에게 확인 후 불필요하면 삭제를 권장합니다.

---

## 폴더 구조

```
GPT_automation/
├── README.md                          # 이 문서
├── .env.example                       # 환경변수 템플릿 (CLI 스크립트용)
├── .env                                # 실제 환경변수 (git 제외 · 직접 생성)
├── requirements.txt                    # 전체 의존성 (CLI + gpt_manager)
├── reset_gpt_accounts.py               # 계정 초기화 (CLI · 순차)
├── reset_gpt_accounts_parallel.py      # 계정 초기화 (CLI · 병렬, Chrome 버전 자동감지)
├── add_members.py                      # 멤버 추가 (CLI)
├── crawl_agency_emails.py              # [별개 기능] 수행기관 이메일 수집
├── fix_indent.py                       # 1회성 개발 유틸 (재실행 금지)
├── tt.py                               # 용도 불명확 · 실행 불가 (위 설명 참고)
├── list.xlsx                           # add_members.py 입력 예시
├── 수행기관조회_20260520.xls            # crawl_agency_emails.py 입력
├── 수행기관조회_이메일수집_테스트.xlsx    # crawl_agency_emails.py 출력 예시
├── chrome_extension.zip 등             # 웹스토어 업로드용 빌드 산출물
│
├── gpt_manager/                        # ⭐ 배포용 GUI 앱
│   ├── app.py                          # FastAPI 서버 진입점
│   ├── config.json                     # 실제 인증정보 저장 (git 제외)
│   ├── requirements.txt                # gpt_manager 전용 의존성
│   ├── build.py / build_mac.sh / build_win.bat   # 실행파일 빌드 스크립트
│   ├── diagnose_project_delete.py      # 개발자용 진단 도구
│   ├── utils/                          # 설정 로드, IMAP 인증코드 추출
│   ├── engines/                        # 초기화 · 멤버추가 핵심 로직
│   └── static/                         # 웹 UI (HTML/CSS/JS)
│
└── chrome_extension/                   # 멤버 추가 전용 Chrome 확장 프로그램
    ├── README.md                       # 상세 사용·배포 가이드 (별도 작성됨)
    ├── manifest.json
    ├── popup.html / popup.js
    ├── background.js / content.js
    └── icon.png
```

---

## 배포 시 반드시 확인할 것 (보안)

- `.env`와 `gpt_manager/config.json`은 이미 `.gitignore`에 등록되어 있어 git 저장소에는 올라가지 않습니다 (확인됨).
- **하지만 `gpt_manager`를 실행 파일로 빌드해서 zip으로 압축해 동료에게 전달할 경우, PyInstaller가 만든 `dist/` 폴더나 실행 파일 옆에 `config.json`이 이미 채워진 채로 함께 배포되지 않도록 주의하세요.** 그대로 전달하면 마스터 이메일의 앱 비밀번호와 공통 비밀번호가 전달받는 사람 모두에게 그대로 노출됩니다.
- 저장소 폴더 전체를 압축해서 넘길 때도 `.env` 파일은 반드시 제외하고 전달하세요.
- 위 3가지 인증 정보는 슬랙/이메일 등 평문 채널로 공유하지 말고, 직접 전달하거나 비밀번호 관리 도구를 이용하는 것을 권장합니다.

---

## 문제 해결

| 증상 | 원인/해결 |
|---|---|
| Chrome 실행은 되는데 로그인 단계에서 계속 멈춤 | ChatGPT 화면 구성이 바뀌었을 수 있습니다. 터미널에 뜨는 안내에 따라 Enter를 눌러 수동으로 진행할 수 있습니다. |
| "크롬 브라우저를 찾을 수 없습니다" 오류 | 시스템에 실제 Google Chrome이 설치되어 있는지 확인하세요 (Chromium이나 다른 브라우저는 지원하지 않습니다). |
| 인증 코드를 계속 못 찾음 | 마스터 이메일/앱 비밀번호가 올바른지, 해당 Gmail의 "전체보관함"에 OpenAI 인증 메일이 실제로 들어오는지 확인하세요. |
| `reset_gpt_accounts.py`만 유독 실행이 안 됨 | 최근 Chrome이 업데이트되었다면 하드코딩된 `version_main=147`이 원인일 수 있습니다. `reset_gpt_accounts_parallel.py`를 대신 사용하세요. |
| 멤버 추가 시 "회원 추가" 버튼을 못 찾는다는 오류 | Google Workspace **관리자** 계정으로 로그인되어 있는지 확인하세요. 일반 계정은 권한이 없습니다. |
| 이미 등록된 사람도 실패로 표시됨 | 사후 확인 로직이 있어 대부분 자동으로 "이미 추가됨"으로 처리되지만, 실패로 남은 항목만 다시 실행해도 안전합니다 (중복 추가되지 않음). |

---

## 문의

담당자: **국필호 (피터)** — `peter@ablearn.kr` *(앱 사이드바에 기재된 연락처 기준)*
