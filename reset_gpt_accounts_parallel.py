import os
import re
import time
import sys
import shutil
import imaplib
import email
import email.utils
import tempfile
from datetime import datetime, timezone, timedelta
from email.header import decode_header
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# .env 파일 로드
load_dotenv()

# ================= 설정 부분 =================
MASTER_EMAIL = os.getenv("MASTER_EMAIL")
APP_PASSWORD = os.getenv("APP_PASSWORD")
COMMON_PASSWORD = os.getenv("COMMON_PASSWORD")

MAX_WORKERS = 2  # 동시 최대 실행 수
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
    return sorted(list(set(numbers)))


def log(tag, msg):
    """계정 태그를 붙여 로그 출력 (스레드 안전)"""
    print(f"[{tag}] {msg}", flush=True)


def get_openai_code(email_user, email_pass, target_email, login_timestamp=None, max_retries=10, delay=5, tag=""):
    """IMAP을 사용하여 이메일함에서 OpenAI 인증 코드를 추출합니다."""
    log(tag, f"📧 이메일 인증 코드 확인 중...")
    
    if login_timestamp is None:
        login_timestamp = datetime.now(timezone.utc) - timedelta(minutes=2)
    
    for attempt in range(max_retries):
        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(email_user, email_pass)
            mail.select('"[Gmail]/&yATMtLz0rQDVaA-"')

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

            found_code = None
            for mail_id in reversed(mail_ids[-20:]):
                status, msg_data = mail.fetch(mail_id, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        sender = str(msg.get("From", "")).lower()
                        if "openai" not in sender and "chatgpt" not in sender and target_email.lower() not in sender:
                            continue

                        # ★ 수신자(To) 확인 — 병렬 처리 시 다른 계정의 코드 혼동 방지
                        to_header = str(msg.get("To", "")).lower()
                        delivered_to = str(msg.get("Delivered-To", "")).lower()
                        x_original_to = str(msg.get("X-Original-To", "")).lower()
                        if (target_email.lower() not in to_header 
                            and target_email.lower() not in delivered_to 
                            and target_email.lower() not in x_original_to):
                            continue

                        try:
                            mail_date = email.utils.parsedate_to_datetime(msg.get("Date"))
                            if mail_date < login_timestamp:
                                continue
                        except Exception:
                            pass

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

                        body = re.sub(r'<style[^>]*>.*?</style>', ' ', body, flags=re.DOTALL|re.IGNORECASE)
                        body = re.sub(r'<[^>]+>', ' ', body)
                        body = re.sub(r'#\d{6}', ' ', body)

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
            log(tag, f"⚠️ 이메일 확인 중 오류: {e}")
        
        log(tag, f"⏳ 인증 코드 대기 중... ({attempt + 1}/{max_retries})")
        time.sleep(delay)

    log(tag, "❌ 인증 코드를 찾을 수 없습니다.")
    return None


def process_account(num):
    """하나의 계정에 대한 전체 초기화 프로세스 (독립 스레드에서 실행)"""
    target_email = f"gpt{num}@ablearn.kr"
    tag = f"gpt{num}"
    
    # 독립 Chrome 프로필 디렉토리 생성
    profile_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_gpt{num}")
    
    log(tag, "=========================================================")
    log(tag, f"🚀 작업 시작: {target_email}")
    
    for overall_attempt in range(3):
        if overall_attempt > 0:
            log(tag, f"🔄 브라우저 재시작 및 전체 과정 재시도 중... (시도 {overall_attempt + 1}/3)")
            
        driver = None
        try:
            # 독립 Chrome 인스턴스 생성
            options = uc.ChromeOptions()
            options.add_argument(f"--user-data-dir={profile_dir}")
            driver = uc.Chrome(options=options, version_main=147)
            driver.set_window_size(1920, 1080)
            
            # ===== 1. 로그인 =====
            driver.get("https://chatgpt.com")
            
            try:
                login_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='login-button']"))
                )
                login_btn.click()
            except:
                log(tag, "⚠️ 'Log in' 버튼을 찾지 못했습니다.")
                if overall_attempt == 0: continue
                return {"email": target_email, "status": "FAIL", "reason": "로그인 버튼 없음"}

            # 이메일 입력
            login_request_time = datetime.now(timezone.utc) - timedelta(seconds=5)
            email_entered = False
            for attempt in range(3):
                try:
                    email_input = WebDriverWait(driver, 5).until(
                        EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']"))
                    )
                    email_input.send_keys(target_email)
                    email_input.send_keys(Keys.RETURN)
                    email_entered = True
                    break
                except:
                    if attempt < 2:
                        log(tag, f"⚠️ 이메일 입력창 재시도... ({attempt + 1}/2)")
                        time.sleep(3)
            
            if not email_entered:
                log(tag, "❌ 이메일 입력창을 찾지 못했습니다.")
                if overall_attempt == 0: continue
                return {"email": target_email, "status": "FAIL", "reason": "이메일 입력창 없음"}

            # 비밀번호 또는 인증 코드 입력 대기
            log(tag, "💡 비밀번호/인증 코드 대기...")
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
                log(tag, "🔑 비밀번호 입력")
                try:
                    pw_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                    pw_input.send_keys(COMMON_PASSWORD)
                    pw_input.send_keys(Keys.RETURN)
                    time.sleep(3)
                    if driver.find_elements(By.CSS_SELECTOR, "input[inputmode='numeric'], input[name='code']") or "code" in driver.current_url.lower():
                        found_code = True
                except:
                    pass
        
            if found_code:
                log(tag, "📩 인증 코드 필요")
                code = get_openai_code(MASTER_EMAIL, APP_PASSWORD, target_email, login_timestamp=login_request_time, tag=tag)
                if code:
                    log(tag, f"✅ 인증 코드: {code}")
                    try:
                        code_inputs = driver.find_elements(By.CSS_SELECTOR, "input[inputmode='numeric'], input[name='code']")
                        if code_inputs:
                            code_inputs[0].send_keys(code)
                            code_inputs[0].send_keys(Keys.RETURN)
                    except:
                        log(tag, f"⚠️ 인증 코드 자동 입력 실패")
                else:
                    return {"email": target_email, "status": "FAIL", "reason": "인증 코드 수신 실패"}

            # 로그인 완료 대기
            log(tag, "⏳ 로그인 완료 대기...")
            login_done = False
            for _ in range(30):
                try:
                    if driver.find_elements(By.ID, "prompt-textarea"):
                        login_done = True
                        break
                    account_btns = driver.find_elements(By.CSS_SELECTOR, "fieldset > button")
                    if len(account_btns) >= 2:
                        log(tag, "➡️ 계정 선택 — 첫 번째 계정")
                        driver.execute_script("arguments[0].click();", account_btns[0])
                        time.sleep(3)
                        continue
                except:
                    pass
                time.sleep(1)

            if not login_done:
                try:
                    WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.ID, "prompt-textarea"))
                    )
                    login_done = True
                except:
                    log(tag, "❌ 로그인 실패")
                    return {"email": target_email, "status": "FAIL", "reason": "로그인 타임아웃"}

            log(tag, "🟢 로그인 성공!")

            # ===== 2. 초기화 작업 =====
            log(tag, "⚙️ 초기화 작업 시작...")
        
            # --- (C) 채팅 기록 모두 삭제 ---
            log(tag, "➡️ 데이터 제어 > 모두 삭제")
            driver.get("https://chatgpt.com/#settings/DataControls")
            time.sleep(4)

            delete_all_btn = driver.find_elements(
                By.XPATH, "//button[.//div[text()='모두 삭제'] or contains(., '모두 삭제')]"
            )
            if delete_all_btn:
                driver.execute_script("arguments[0].click();", delete_all_btn[0])
                time.sleep(3)
            
                time.sleep(2)
                confirm = driver.find_elements(By.CSS_SELECTOR, "button[data-testid='confirm-delete-all-chats-button']")
                if not confirm:
                    confirm = driver.find_elements(By.CSS_SELECTOR, "button.btn-danger")
                if not confirm:
                    confirm = driver.find_elements(By.XPATH, "//button[contains(., '삭제 확인')]")
                if confirm:
                    driver.execute_script("arguments[0].click();", confirm[0])
                    time.sleep(3)
                    log(tag, "✅ 채팅 기록 삭제 완료")
                else:
                    log(tag, "⚠️ 삭제 확인 버튼 못 찾음")
            else:
                log(tag, "ℹ️ '모두 삭제' 버튼 없음 (이미 비어있음)")

            # --- (A) 라이브러리 삭제 ---
            driver.get("https://chatgpt.com/library")
            time.sleep(5)

            # 전략1: 헤더 bridge button으로 모두 선택
            bulk_selected = False
            driver.execute_script("""
                const header = document.querySelector('[data-page-table-list-header]');
                if (header) {
                    const bridgeBtn = header.querySelector('button');
                    if (bridgeBtn) {
                        const events = ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];
                        events.forEach(type => {
                            bridgeBtn.dispatchEvent(new PointerEvent(type, {
                                bubbles: true, cancelable: true, view: window,
                                pointerId: 1, pointerType: 'mouse'
                            }));
                        });
                    }
                }
            """)
            time.sleep(2)

            checked_count = driver.execute_script(
                "return document.querySelectorAll('input[type=\"checkbox\"]:checked').length;"
            )
            if checked_count > 0:
                bulk_selected = True
                log(tag, f"➡️ 모두 선택 — {checked_count}개")

            # 전략2: 개별 bridge buttons
            if not bulk_selected:
                clicked = driver.execute_script("""
                    const bridges = document.querySelectorAll('button[data-testid^="artifact-checkbox-bridge-"]');
                    let c = 0;
                    bridges.forEach(btn => {
                        ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(type => {
                            btn.dispatchEvent(new PointerEvent(type, {bubbles:true,cancelable:true,view:window,pointerId:1,pointerType:'mouse'}));
                        });
                        c++;
                    });
                    return c;
                """)
                time.sleep(2)
                checked_count = driver.execute_script("return document.querySelectorAll('input[type=\"checkbox\"]:checked').length;")
                if checked_count > 0:
                    bulk_selected = True
                    log(tag, f"➡️ 개별 선택 — {checked_count}개")

            if bulk_selected:
                bulk_del = driver.find_elements(By.XPATH, "//button[contains(., '삭제')]")
                if bulk_del:
                    driver.execute_script("arguments[0].click();", bulk_del[0])
                    time.sleep(2)
                    confirm_btns = driver.find_elements(By.CSS_SELECTOR, "button[data-testid='confirm-delete-recall-file-button']")
                    if not confirm_btns:
                        confirm_btns = driver.find_elements(By.CSS_SELECTOR, "button.btn-danger")
                    if not confirm_btns:
                        confirm_btns = driver.find_elements(By.XPATH, "//button[.//div[text()='삭제']]")
                    if confirm_btns:
                        driver.execute_script("arguments[0].click();", confirm_btns[-1])
                        time.sleep(3)
                        log(tag, "✅ 라이브러리 일괄 삭제 완료")
            else:
                log(tag, "ℹ️ 라이브러리 일괄 선택 실패 — 개별 삭제 시도")

            # 개별 삭제 폴백
            lib_count = 0
            for _ in range(100):
                time.sleep(1)
                action_btns = driver.find_elements(By.CSS_SELECTOR, "button[data-page-table-row-actions-focus-target]")
                if not action_btns:
                    log(tag, f"📂 라이브러리 {lib_count}개 삭제 완료")
                    break
                driver.execute_script("arguments[0].click();", action_btns[0])
                time.sleep(1)
                del_menu = driver.find_elements(By.XPATH, "//div[@role='menuitem' and contains(., '삭제')]")
                if not del_menu:
                    del_menu = driver.find_elements(By.XPATH, "//*[@role='menu']//*[contains(text(), '삭제')]")
                if del_menu:
                    driver.execute_script("arguments[0].click();", del_menu[0])
                    time.sleep(2)
                    cfm = driver.find_elements(By.CSS_SELECTOR, "button[data-testid='confirm-delete-recall-file-button']")
                    if not cfm:
                        cfm = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-danger') and contains(., '삭제')]")
                    if not cfm:
                        cfm = driver.find_elements(By.XPATH, "//button[.//div[text()='삭제']]")
                    if cfm:
                        driver.execute_script("arguments[0].click();", cfm[-1])
                        time.sleep(2)
                        lib_count += 1
                    else:
                        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        break
                else:
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    break

            # --- (B) 프로젝트 삭제 ---
            for _ in range(200):
                option_btns = driver.find_elements(By.CSS_SELECTOR, "button[data-trailing-button]")
                if not option_btns:
                    log(tag, "➡️ 프로젝트 삭제 완료")
                    break
                driver.execute_script("arguments[0].click();", option_btns[0])
                time.sleep(1)
                del_items = driver.find_elements(By.XPATH, "//*[contains(text(), '프로젝트 삭제') or contains(text(), '삭제')]")
                clicked = False
                for item in del_items:
                    if '삭제' in item.text.strip():
                        driver.execute_script("arguments[0].click();", item)
                        time.sleep(3)
                        cfm = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-danger')] | //dialog//button[contains(., '삭제')]")
                        if not cfm:
                            cfm = driver.find_elements(By.XPATH, "//button[.//div[text()='삭제']]")
                        if cfm:
                            driver.execute_script("arguments[0].click();", cfm[-1])
                            time.sleep(3)
                        clicked = True
                        break
                if not clicked:
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    break

            # --- (D) 보안 → 모두 로그아웃 ---
            log(tag, "➡️ 보안 > 모두 로그아웃")
            driver.get("https://chatgpt.com/#settings/Security")
            time.sleep(4)

            logout_btn = driver.find_elements(By.CSS_SELECTOR, "[data-testid='logout-all-button']")
            if not logout_btn:
                logout_btn = driver.find_elements(By.XPATH, "//button[contains(., '모두 로그아웃')]")
            if logout_btn:
                driver.execute_script("arguments[0].click();", logout_btn[0])
                time.sleep(3)
                confirm_logout = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-danger') and contains(., '모든 기기에서 로그아웃')]")
                if not confirm_logout:
                    confirm_logout = driver.find_elements(By.XPATH, "//button[.//div[contains(text(), '모든 기기에서 로그아웃')]]")
                if confirm_logout:
                    driver.execute_script("arguments[0].click();", confirm_logout[-1])
                    time.sleep(5)
                    log(tag, "✅ 모든 기기에서 로그아웃 완료")
                else:
                    log(tag, "⚠️ 로그아웃 확인 버튼 못 찾음")
            else:
                log(tag, "⚠️ '모두 로그아웃' 버튼 없음")

            log(tag, f"✅ {target_email} 초기화 완료!")
            return {"email": target_email, "status": "OK"}

        except Exception as e:
            log(tag, f"❌ 에러 발생: {e}")
            if overall_attempt == 2:
                return {"email": target_email, "status": "FAIL", "reason": str(e)}
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            # 임시 프로필 폴더 정리
            try:
                if os.path.exists(profile_dir):
                    shutil.rmtree(profile_dir, ignore_errors=True)
            except:
                pass
                
    return {"email": target_email, "status": "FAIL", "reason": "최대 재시도 횟수 초과"}


def main():
    print("=========================================================")
    print("GPT 계정 자동 초기화 스크립트 (병렬 버전, 최대 3개 동시)")
    print("=========================================================")
    
    range_input = input("작업할 계정의 숫자 범위를 입력하세요 (예: 1~10, 12, 15~17): ")
    target_numbers = parse_ranges(range_input)
    
    if not target_numbers:
        print("❌ 유효한 계정 번호가 없습니다.")
        sys.exit(1)
        
    print(f"총 {len(target_numbers)}개의 계정, 최대 {MAX_WORKERS}개 동시 실행: {target_numbers}")
    print("=========================================================\n")
    
    results = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_account, num): num for num in target_numbers}
        
        for future in as_completed(futures):
            num = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({"email": f"gpt{num}@ablearn.kr", "status": "FAIL", "reason": str(e)})
    
    elapsed = time.time() - start_time
    
    # 결과 요약
    print("\n=========================================================")
    print("📊 작업 결과 요약")
    print("=========================================================")
    ok_count = 0
    fail_count = 0
    for r in sorted(results, key=lambda x: x["email"]):
        if r["status"] == "OK":
            print(f"  ✅ {r['email']}")
            ok_count += 1
        else:
            print(f"  ❌ {r['email']} — {r.get('reason', '알 수 없음')}")
            fail_count += 1
    
    print(f"\n성공: {ok_count}개 | 실패: {fail_count}개 | 소요 시간: {elapsed:.0f}초")
    print("🎉 모든 작업이 끝났습니다!")


if __name__ == "__main__":
    main()
