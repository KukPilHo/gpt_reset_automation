import os
import re
import time
import sys
import imaplib
import email
import email.utils
from datetime import datetime, timezone, timedelta
from email.header import decode_header
from dotenv import load_dotenv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# .env 파일 로드
load_dotenv()

# ================= 설정 부분 =================
# 마스터 이메일 (모든 인증 코드가 모이는 이메일)
MASTER_EMAIL = os.getenv("MASTER_EMAIL")
# 마스터 이메일 앱 비밀번호 (띄어쓰기 없이 16자리)
APP_PASSWORD = os.getenv("APP_PASSWORD")

# 공통 비밀번호
COMMON_PASSWORD = os.getenv("COMMON_PASSWORD")
# ===========================================

def parse_ranges(range_str):
    """'1~10, 12, 15~17' 형식의 문자열을 정수 리스트로 변환합니다."""
    numbers = []
    parts = [p.strip() for p in range_str.split(',')]
    for part in parts:
        if not part:
            continue
        if '~' in part:
            try:
                start_str, end_str = part.split('~')
                start = int(start_str)
                end = int(end_str)
                numbers.extend(range(start, end + 1))
            except ValueError:
                print(f"⚠️ 경고: 잘못된 범위 형식입니다 '{part}'")
        else:
            try:
                numbers.append(int(part))
            except ValueError:
                print(f"⚠️ 경고: 잘못된 숫자 형식입니다 '{part}'")
    
    # 중복 제거 및 정렬
    return sorted(list(set(numbers)))

def get_openai_code(email_user, email_pass, target_email, max_retries=10, delay=5):
    """
    IMAP을 사용하여 이메일함에 접속한 후, OpenAI에서 온 가장 최근의 6자리 인증 코드를 추출합니다.
    """
    print(f"📧 [{target_email}] 이메일 인증 코드 확인 중...")
    
    for attempt in range(max_retries):
        try:
            # Gmail IMAP 서버 연결
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(email_user, email_pass)
            # 받은편지함 대신 '전체보관함(All Mail)' 선택
            mail.select('"[Gmail]/&yATMtLz0rQDVaA-"')

            # 받은편지함의 모든 메일 검색
            status, messages = mail.search(None, 'ALL')
            if status != "OK":
                mail.logout()
                time.sleep(delay)
                continue

            mail_ids = messages[0].split()
            if not mail_ids:
                mail.logout()
                time.sleep(delay)
                continue

            # 가장 최신 메일부터 역순으로 최대 20개 확인
            found_code = None
            for mail_id in reversed(mail_ids[-20:]):
                status, msg_data = mail.fetch(mail_id, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # 발신자 확인 (포워딩된 메일인 경우 발신자가 gpt8@ablearn.kr 로 찍힐 수 있음)
                        sender = str(msg.get("From", "")).lower()
                        if "openai" not in sender and "chatgpt" not in sender and target_email.lower() not in sender:
                            continue

                        # 메일 수신 시간 확인 (오래된 과거 메일 무시)
                        try:
                            mail_date = email.utils.parsedate_to_datetime(msg.get("Date"))
                            if datetime.now(timezone.utc) - mail_date > timedelta(minutes=10):
                                continue # 10분 이상 지난 과거 메일은 무시하고 계속 대기
                        except Exception as e:
                            print(f"시간 파싱 에러 (무시됨): {e}")

                        # 메일 본문 추출
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                content_disposition = str(part.get("Content-Disposition"))
                                
                                if content_type == "text/plain" and "attachment" not in content_disposition:
                                    body = part.get_payload(decode=True).decode(errors='replace')
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode(errors='replace')

                        # HTML 태그 및 style 태그 내용 제거
                        body = re.sub(r'<style[^>]*>.*?</style>', ' ', body, flags=re.DOTALL|re.IGNORECASE)
                        body = re.sub(r'<[^>]+>', ' ', body)
                        # #으로 시작하는 헥사코드 제거 방어코드
                        body = re.sub(r'#\d{6}', ' ', body)

                        # 6자리 연속된 숫자(인증코드) 정규식으로 찾기
                        match = re.search(r'(?<!\d)(\d{6})(?!\d)', body)
                        if match:
                            found_code = match.group(1)
                            break
                
                if found_code:
                    break
            
            mail.logout()
            
            if found_code:
                return found_code
        except Exception as e:
            print(f"⚠️ 이메일 확인 중 오류 발생: {e}")
        
        print(f"⏳ 인증 코드를 기다리는 중... (시도 {attempt + 1}/{max_retries})")
        time.sleep(delay)

    print("❌ 인증 코드를 찾을 수 없습니다.")
    return None

def login_and_reset(driver, target_email):
    """하나의 계정에 대해 로그인 및 초기화 동작을 수행합니다."""
    print(f"\n=========================================================")
    print(f"🚀 작업을 시작합니다: {target_email}")
    
    try:
        # 1. ChatGPT 로그인 페이지 이동
        driver.get("https://chatgpt.com")
        
        # 'Log in' 버튼 대기 및 클릭 (선택자가 변경될 수 있으므로 주의)
        try:
            login_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='login-button']"))
            )
            login_btn.click()
        except:
            print("⚠️ 'Log in' 버튼을 자동으로 찾지 못했습니다.")
            input("👉 직접 'Log in' 버튼을 누르시고, 이메일 입력창이 나오면 터미널에서 [Enter]를 누르세요...")

        # 2. 이메일 입력
        try:
            email_input = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']"))
            )
            email_input.send_keys(target_email)
            email_input.send_keys(Keys.RETURN)
        except:
            print("⚠️ 이메일 입력창을 자동으로 찾지 못했습니다.")
            input("👉 직접 이메일을 입력하시고 다음 단계로 넘어가면 터미널에서 [Enter]를 누르세요...")

        # 3. 비밀번호 또는 인증 코드 입력 대기
        print("💡 비밀번호 또는 인증 코드 입력을 대기합니다...")
        
        # 최대 10초 동안 비밀번호 창이나 인증 코드 창이 뜰 때까지 반복 확인
        found_pw = False
        found_code = False
        
        for _ in range(10):
            try:
                if driver.find_elements(By.CSS_SELECTOR, "input[type='password']"):
                    found_pw = True
                    break
                if driver.find_elements(By.CSS_SELECTOR, "input[inputmode='numeric'], input[name='code']") or "code" in driver.current_url.lower():
                    found_code = True
                    break
            except:
                pass
            time.sleep(1)
        
        if found_pw:
            print("🔑 비밀번호 입력창 발견.")
            try:
                pw_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                pw_input.send_keys(COMMON_PASSWORD)
                pw_input.send_keys(Keys.RETURN)
                time.sleep(3)
                # 비밀번호 입력 후 인증 코드를 요구할 수도 있으니 한 번 더 체크
                if driver.find_elements(By.CSS_SELECTOR, "input[inputmode='numeric'], input[name='code']") or "code" in driver.current_url.lower():
                    found_code = True
            except:
                pass
        
        if found_code:
            print("📩 이메일 인증 코드가 필요합니다.")
            code = get_openai_code(MASTER_EMAIL, APP_PASSWORD, target_email)
            if code:
                print(f"✅ 인증 코드 추출 완료: {code}")
                try:
                    # OTP 입력창들이 여러 개일 수 있으므로 첫 번째를 찾아 입력 (보통 자동 완성됨)
                    code_inputs = driver.find_elements(By.CSS_SELECTOR, "input[inputmode='numeric'], input[name='code']")
                    if code_inputs:
                        code_input = code_inputs[0]
                        code_input.send_keys(code)
                        # 마지막 입력창에서 엔터 키를 전송하여 로그인 시도 (계속 버튼 역할)
                        code_input.send_keys(Keys.RETURN)
                except:
                    print(f"👉 브라우저에 인증 코드({code})를 직접 입력해주세요.")
            else:
                input("👉 인증 코드를 메일함에서 확인하여 직접 입력하신 후 [Enter]를 누르세요...")

        # 4. 로그인 완료 대기
        print("⏳ 로그인 완료를 기다립니다...")
        try:
            WebDriverWait(driver, 15).until(
                EC.visibility_of_element_located((By.ID, "prompt-textarea"))
            )
            print("🟢 로그인 성공!")
        except:
            print("⚠️ 로그인 완료를 자동으로 감지하지 못했습니다.")
            input("👉 로그인이 완료되어 채팅창이 보이면 터미널에서 [Enter]를 누르세요...")

        # ------------------------------------------------------------------
        # 5. 초기화 작업 (사용자 커스텀 플로우)
        # ------------------------------------------------------------------
        print("⚙️ 초기화(삭제) 작업을 수행합니다...")
        
        try:
            # 라이브러리 페이지로 이동
            driver.get("https://chatgpt.com/library")
            time.sleep(5) # 페이지 로딩 대기
            
            # (1) '모두 선택' 후 삭제
            select_all_btns = driver.find_elements(By.CSS_SELECTOR, "[aria-label='모두 선택']")
            if select_all_btns:
                print("➡️ '모두 선택' 버튼 클릭")
                # ElementClickInterceptedException 방지를 위해 JavaScript로 클릭
                driver.execute_script("arguments[0].click();", select_all_btns[0])
                time.sleep(1)
                
                # 삭제 버튼 클릭 (버튼이 아니라 div 태그로 되어있고 gap-1.5 클래스가 포함됨)
                delete_btns = driver.find_elements(By.XPATH, "//div[contains(@class, 'gap-1.5') and contains(., '삭제')]")
                if delete_btns:
                    print("➡️ '삭제' 버튼 클릭")
                    # 여러 개가 잡힐 수 있으니 가장 마지막에 렌더링된 요소나 첫 번째 요소를 클릭
                    # 안전하게 첫 번째 요소를 클릭합니다.
                    driver.execute_script("arguments[0].click();", delete_btns[0])
                    time.sleep(3) # 모달이 뜨는 애니메이션 대기 (2~3초)
                    
                    # 확인 모달의 삭제 버튼 클릭 (정확히 class="flex items-center justify-center" 이고 텍스트가 "삭제"인 div)
                    confirm_btns = driver.find_elements(By.XPATH, "//div[@class='flex items-center justify-center' and text()='삭제']")
                    if confirm_btns:
                        print("➡️ '삭제(확인)' 버튼 클릭")
                        driver.execute_script("arguments[0].click();", confirm_btns[-1])
                        time.sleep(3)
            
            # (2) 남은 프로젝트 개별 삭제 루프
            while True:
                # 사용자가 제공한 HTML 구조 기반으로 프로젝트 옵션 버튼 찾기
                option_btns = driver.find_elements(By.CSS_SELECTOR, "button[data-trailing-button]")
                if not option_btns:
                    print("➡️ 삭제할 프로젝트가 더 이상 없습니다.")
                    break
                
                print("➡️ '프로젝트 옵션 열기' 클릭")
                driver.execute_script("arguments[0].click();", option_btns[0])
                time.sleep(1)
                
                # '프로젝트 삭제' 텍스트를 가진 메뉴 항목 클릭
                del_proj_menus = driver.find_elements(By.XPATH, "//*[contains(text(), '프로젝트 삭제')]")
                if del_proj_menus:
                    print("➡️ '프로젝트 삭제' 클릭")
                    driver.execute_script("arguments[0].click();", del_proj_menus[0])
                    time.sleep(3) # 모달이 뜨는 애니메이션 대기
                    
                    # 확인 창의 '삭제' 클릭 (div나 button 모두 커버)
                    confirm_btns = driver.find_elements(By.XPATH, "//*[contains(text(), '삭제') or contains(., '삭제')]")
                    if confirm_btns:
                        print("➡️ '삭제(확인)' 클릭")
                        driver.execute_script("arguments[0].click();", confirm_btns[-1])
                        time.sleep(3)
                else:
                    # 메뉴가 안 뜨면 무한 루프 방지
                    break

            # (3) 설정 메뉴 진입
            print("➡️ 프로필 버튼 클릭")
            profile_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='accounts-profile-button']"))
            )
            driver.execute_script("arguments[0].click();", profile_btn)
            time.sleep(1)
            
            print("➡️ '설정' 클릭")
            # 설정 메뉴는 고유 testid를 사용하여 완벽하게 탐색
            settings_menus = driver.find_elements(By.CSS_SELECTOR, "[data-testid='settings-menu-item']")
            if settings_menus:
                driver.execute_script("arguments[0].click();", settings_menus[0])
                time.sleep(2)
            else:
                print("⚠️ '설정' 버튼을 찾지 못했습니다.")

        except Exception as e:
            print(f"⚠️ 초기화 단계 자동 클릭 중 오류 발생: {e}")
        
        print("🚨 [1차 구현 완료] 여기까지 코드가 구현되었습니다.")
        input("👉 결과 확인 및 수동 로그아웃 후 다음 계정으로 넘어가려면 [Enter]를 누르세요...")
        
        print("✅ 작업 완료. 컨텍스트를 초기화합니다.")

    except Exception as e:
        print(f"❌ 작업 중 에러 발생: {e}")
        input("👉 브라우저 상태를 확인하시고, 문제를 해결한 뒤 다음 계정으로 넘어가려면 [Enter]를 누르세요...")

def main():
    print("=========================================================")
    print("GPT 계정 자동 초기화 스크립트 (Undetected Chromedriver 버젼)")
    print("=========================================================")
    
    range_input = input("작업할 계정의 숫자 범위를 입력하세요 (예: 1~10, 12, 15~17): ")
    target_numbers = parse_ranges(range_input)
    
    if not target_numbers:
        print("❌ 유효한 계정 번호가 없습니다.")
        sys.exit(1)
        
    print(f"총 {len(target_numbers)}개의 계정에 대해 작업을 시작합니다: {target_numbers}")
    
    # 봇 탐지 우회를 위해 undetected_chromedriver 사용
    options = uc.ChromeOptions()
    # 필요하다면 프로필 폴더를 지정할 수 있으나 계정 전환을 위해 매번 새 세션 권장
    
    for num in target_numbers:
        target_email = f"gpt{num}@ablearn.kr"
        
        # 매 계정마다 브라우저를 새로 열어 쿠키/세션을 완전 초기화
        # 사용자의 Chrome 버전에 맞게 version_main=147 추가
        driver = uc.Chrome(options=options, version_main=147)
        
        login_and_reset(driver, target_email)
        
        driver.quit()
        time.sleep(2) # 다음 계정으로 넘어가기 전 잠시 대기
            
    print("\n🎉 모든 계정의 작업이 끝났습니다!")

if __name__ == "__main__":
    main()
