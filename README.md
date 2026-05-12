# gpt_reset_automation

GPT 계정 자동 초기화 및 Google Groups 멤버 자동 추가 스크립트입니다.

## 기능

- **reset_gpt_accounts.py**: ChatGPT 계정 로그인 → 라이브러리/프로젝트 일괄 삭제 → 설정 초기화
- **add_members.py**: 엑셀 파일 기반 Google Groups 멤버 자동 추가 (Playwright)
- **chrome_extension/**: Google Groups 멤버 추가용 Chrome 확장 프로그램

## 설치

```bash
pip install -r requirements.txt
```

## 환경 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고, 실제 값을 입력합니다.

```bash
cp .env.example .env
# .env 파일을 열어 실제 이메일/비밀번호를 입력하세요
```

## 사용법

```bash
python reset_gpt_accounts.py
```
