python
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# 1. 설정
CLIENT_SECRET_FILE = os.path.expanduser('~/Downloads/client_secret.json')
TOKEN_FILE = os.path.expanduser('~/.hermes/token.json')
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive'
]

def main():
    # 2. 인증 플로우 설정
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE, SCOPES
    )

    # 3. 로컬 서버를 통한 인증 수행
    # run_local_server는 브라우저를 자동으로 열고 인증 코드를 기다립니다.
    creds = flow.run_local_server(port=0)

    # 4. 토큰 저장 디렉토리 확인 및 저장
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, 'w') as token:
        token.write(creds.to_json())
    
    print(f"인증 성공! 토큰이 {TOKEN_FILE}에 저장되었습니다.")

if __name__ == '__main__':
    main()