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
from selenium.webdriver.common.action_chains import ActionChains

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

def get_openai_code(email_user, email_pass, target_email, login_timestamp=None, max_retries=10, delay=5):
    """
    IMAP을 사용하여 이메일함에 접속한 후, OpenAI에서 온 가장 최근의 6자리 인증 코드를 추출합니다.
    login_timestamp: 로그인 요청 시점의 UTC datetime. 이 시점 이후에 온 메일만 인정합니다.
    """
    print(f"📧 [{target_email}] 이메일 인증 코드 확인 중...")
    
    # login_timestamp가 없으면 기본값: 현재 시각 - 2분 (안전 마진)
    if login_timestamp is None:
        login_timestamp = datetime.now(timezone.utc) - timedelta(minutes=2)
    
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

                        # 메일 수신 시간 확인 — 로그인 요청 시점 이후의 메일만 인정
                        try:
                            mail_date = email.utils.parsedate_to_datetime(msg.get("Date"))
                            if mail_date < login_timestamp:
                                continue  # 로그인 버튼 누르기 전에 온 메일은 무시
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
        # ★ 로그인 요청 시점 기록 (이 시점 이후에 온 인증 코드만 사용)
        login_request_time = datetime.now(timezone.utc) - timedelta(seconds=5)  # 5초 여유
        email_entered = False
        for attempt in range(3):  # 최대 3회 시도
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
                    print(f"⚠️ 이메일 입력창을 찾지 못했습니다. 재시도 중... ({attempt + 1}/2)")
                    time.sleep(3)
        if not email_entered:
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
            code = get_openai_code(MASTER_EMAIL, APP_PASSWORD, target_email, login_timestamp=login_request_time)
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

        # 4. 로그인 완료 대기 (계정 선택 화면 처리 포함)
        print("⏳ 로그인 완료를 기다립니다...")
        login_done = False
        for _ in range(30):  # 최대 30초 대기
            try:
                # 채팅창이 보이면 로그인 완료
                if driver.find_elements(By.ID, "prompt-textarea"):
                    print("🟢 로그인 성공!")
                    login_done = True
                    break

                # 계정 선택 화면 (에이블런 계정 / gpt 계정) 처리
                # fieldset 안에 button이 여러 개 있는 구조
                account_btns = driver.find_elements(By.CSS_SELECTOR, "fieldset > button")
                if len(account_btns) >= 2:
                    print("➡️ 계정 선택 화면 감지 — 첫 번째 계정 선택")
                    driver.execute_script("arguments[0].click();", account_btns[0])
                    time.sleep(3)
                    continue
            except:
                pass
            time.sleep(1)

        if not login_done:
            # 마지막으로 한 번 더 확인
            try:
                WebDriverWait(driver, 10).until(
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
            # ===== (C) 설정 → 데이터 제어 → 모두 삭제 (채팅 기록 먼저 삭제) =====
            # URL 직접 이동으로 프로필/설정/탭 클릭 과정 생략
            print("➡️ 설정 > 데이터 제어 페이지로 이동")
            driver.get("https://chatgpt.com/#settings/DataControls")
            time.sleep(4)  # 설정 모달 로딩 대기

            # '모두 삭제' 버튼 클릭
            print("➡️ '모두 삭제' 버튼 클릭")
            delete_all_btn = driver.find_elements(
                By.XPATH,
                "//button[.//div[text()='모두 삭제'] or contains(., '모두 삭제')]"
            )
            if delete_all_btn:
                driver.execute_script("arguments[0].click();", delete_all_btn[0])
                time.sleep(3)  # 확인 팝업 대기

                # 확인 팝업의 '삭제 확인' 클릭
                print("➡️ '삭제 확인' 클릭")
                time.sleep(2)  # 팝업 렌더링 대기
                # 방법1: data-testid (가장 안정적)
                confirm_delete_all = driver.find_elements(
                    By.CSS_SELECTOR, "button[data-testid='confirm-delete-all-chats-button']"
                )
                if not confirm_delete_all:
                    # 방법2: btn-danger 클래스
                    confirm_delete_all = driver.find_elements(
                        By.CSS_SELECTOR, "button.btn-danger"
                    )
                if not confirm_delete_all:
                    # 방법3: '삭제 확인' 텍스트 기반
                    confirm_delete_all = driver.find_elements(
                        By.XPATH,
                        "//button[contains(., '삭제 확인')]"
                    )
                if confirm_delete_all:
                    target_btn = confirm_delete_all[0]
                    driver.execute_script("arguments[0].scrollIntoView(true);", target_btn)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", target_btn)
                    time.sleep(3)
                    print("✅ 채팅 기록 모두 삭제 완료")
                else:
                    print("⚠️ '삭제 확인' 버튼을 찾지 못했습니다.")
            else:
                print("⚠️ '모두 삭제' 버튼을 찾지 못했습니다.")

            # ===== (A) 라이브러리 아이템 삭제 =====
            driver.get("https://chatgpt.com/library")
            time.sleep(5)  # 페이지 로딩 대기

            # ── DOM 진단: 실제 라이브러리 페이지 구조 확인 ──
            diag = driver.execute_script("""
                const info = {};
                info.url = window.location.href;
                info.viewport = { w: window.innerWidth, h: window.innerHeight };
                info.inputs = [];
                document.querySelectorAll('input').forEach(el => {
                    info.inputs.push({
                        type: el.type,
                        ariaLabel: el.getAttribute('aria-label'),
                        ariaHidden: el.getAttribute('aria-hidden'),
                        checked: el.checked,
                        className: el.className.substring(0, 80)
                    });
                });
                info.bridgeButtons = document.querySelectorAll('button[data-testid^="artifact-checkbox-bridge-"]').length;
                info.pageTableHeader = !!document.querySelector('[data-page-table-list-header]');
                info.rows = document.querySelectorAll('[role="row"]').length;
                info.selectableRows = document.querySelectorAll('[data-page-table-selectable-row]').length;
                info.allButtons = document.querySelectorAll('button').length;
                info.threeDotsButtons = document.querySelectorAll('button[aria-label*="작업 메뉴"]').length;
                // 첫 번째 row의 구조 확인
                const firstRow = document.querySelector('[role="row"]');
                if (firstRow) {
                    info.firstRowHTML = firstRow.innerHTML.substring(0, 500);
                }
                return JSON.stringify(info, null, 2);
            """)
            print(f"  [DOM 진단]\n{diag}")

            # ── (A-1) 라이브러리 아이템 전체 선택 후 일괄 삭제 시도 ──
            # React/Radix UI 체크박스는 단순 .click()으로 상태가 안 바뀜
            # 여러 전략을 순차 시도하고, 체크 여부를 확인
            
            bulk_selected = False

            
            # 전략1: 헤더 bridge button에 full mouse event sequence dispatch
            result = driver.execute_script("""
                const header = document.querySelector('[data-page-table-list-header]');
                if (!header) return 'no-header';
                const bridgeBtn = header.querySelector('button');
                if (!bridgeBtn) return 'no-bridge';
                
                // Full pointer/mouse event sequence
                const events = ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'];
                events.forEach(type => {
                    bridgeBtn.dispatchEvent(new PointerEvent(type, {
                        bubbles: true, cancelable: true, view: window,
                        pointerId: 1, pointerType: 'mouse'
                    }));
                });
                
                // 체크 결과 확인
                const checked = document.querySelectorAll('input[type="checkbox"]:checked').length;
                return 'events-dispatched:checked=' + checked;
            """)
            print(f"  [디버그] 전략1 (헤더 bridge event dispatch): {result}")
            time.sleep(2)
            
            # 체크된 게 있으면 성공
            checked_count = driver.execute_script(
                "return document.querySelectorAll('input[type=\"checkbox\"]:checked').length;"
            )
            if checked_count > 0:
                bulk_selected = True
                print(f"➡️ '모두 선택' 성공 — {checked_count}개 체크됨")
            
            # 전략2: 개별 아이템 bridge button 전부 클릭
            if not bulk_selected:
                result2 = driver.execute_script("""
                    const bridges = document.querySelectorAll('button[data-testid^="artifact-checkbox-bridge-"]');
                    let clicked = 0;
                    bridges.forEach(btn => {
                        ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(type => {
                            btn.dispatchEvent(new PointerEvent(type, {
                                bubbles: true, cancelable: true, view: window,
                                pointerId: 1, pointerType: 'mouse'
                            }));
                        });
                        clicked++;
                    });
                    return clicked;
                """)
                print(f"  [디버그] 전략2 (개별 bridge buttons): {result2}개 클릭")
                time.sleep(2)
                
                checked_count = driver.execute_script(
                    "return document.querySelectorAll('input[type=\"checkbox\"]:checked').length;"
                )
                if checked_count > 0:
                    bulk_selected = True
                    print(f"➡️ 개별 선택 성공 — {checked_count}개 체크됨")
            
            # 전략3: Selenium ActionChains로 실제 마우스 클릭
            if not bulk_selected:
                try:
                    cb_el = driver.find_element(
                        By.CSS_SELECTOR, "input[aria-label='모두 선택']"
                    )
                    # 체크박스를 뷰포트로 스크롤 후 ActionChains 클릭
                    driver.execute_script(
                        "arguments[0].closest('.absolute').style.position='relative';"
                        "arguments[0].closest('.absolute').style.left='0';"
                        "arguments[0].closest('.absolute').style.opacity='1';",
                        cb_el
                    )
                    time.sleep(0.5)
                    ActionChains(driver).move_to_element(cb_el).click().perform()
                    time.sleep(2)
                    
                    checked_count = driver.execute_script(
                        "return document.querySelectorAll('input[type=\"checkbox\"]:checked').length;"
                    )
                    if checked_count > 0:
                        bulk_selected = True
                        print(f"➡️ ActionChains 클릭 성공 — {checked_count}개 체크됨")
                    else:
                        print(f"  [디버그] 전략3 (ActionChains): 체크됨 {checked_count}개")
                except Exception as e:
                    print(f"  [디버그] 전략3 실패: {e}")
            
            # 일괄 삭제 실행
            if bulk_selected:
                # 삭제 버튼 찾기
                bulk_delete_btn = driver.find_elements(
                    By.XPATH,
                    "//button[contains(., '삭제')]"
                )
                if bulk_delete_btn:
                    print("➡️ '삭제' 버튼 클릭 (일괄)")
                    driver.execute_script("arguments[0].click();", bulk_delete_btn[0])
                    time.sleep(2)

                    # 확인 모달의 '삭제' 버튼
                    confirm_btns = driver.find_elements(
                        By.CSS_SELECTOR, "button.btn-danger"
                    )
                    if not confirm_btns:
                        confirm_btns = driver.find_elements(
                            By.XPATH,
                            "//button[.//div[text()='삭제']]"
                        )
                    if confirm_btns:
                        print("➡️ '삭제(확인)' 클릭 (일괄)")
                        driver.execute_script("arguments[0].click();", confirm_btns[-1])
                        time.sleep(3)
                        print("✅ 라이브러리 일괄 삭제 완료")
                    else:
                        print("⚠️ 일괄 삭제 확인 버튼을 찾지 못했습니다.")
                else:
                    print("⚠️ 일괄 삭제 버튼이 나타나지 않았습니다.")
            else:
                print("ℹ️ 라이브러리 일괄 선택 실패 — 개별 삭제로 전환합니다.")

            time.sleep(2)

            # ── (A-2) 남은 아이템 개별 삭제 (일괄 삭제가 안 된 경우 폴백) ──
            lib_delete_count = 0
            max_lib_deletes = 100  # 무한루프 방지
            while lib_delete_count < max_lib_deletes:
                time.sleep(1)
                # 라이브러리 행의 ⋯ (작업 메뉴) 버튼 찾기
                action_btns = driver.find_elements(
                    By.CSS_SELECTOR,
                    "button[data-page-table-row-actions-focus-target]"
                )
                if not action_btns:
                    print(f"📂 라이브러리 아이템 {lib_delete_count}개 삭제 완료 (더 이상 없음)")
                    break

                print(f"➡️ 라이브러리 아이템 ⋯ 버튼 클릭 ({lib_delete_count + 1}번째)")
                driver.execute_script("arguments[0].click();", action_btns[0])
                time.sleep(1)

                # 드롭다운 메뉴에서 '삭제' 항목 찾기 (menuitem role 사용)
                delete_menu = driver.find_elements(
                    By.XPATH,
                    "//div[@role='menuitem' and contains(., '삭제')]"
                )
                if not delete_menu:
                    # role=menuitem이 아닌 경우 대비
                    delete_menu = driver.find_elements(
                        By.XPATH,
                        "//div[@data-radix-collection-item]//span[contains(text(), '삭제')]/ancestor::div[@data-radix-collection-item]"
                    )
                if not delete_menu:
                    # 마지막 폴백: 텍스트 기반 검색 (팝오버/드롭다운 내에서)
                    delete_menu = driver.find_elements(
                        By.XPATH,
                        "//*[@role='menu']//*[contains(text(), '삭제')]"
                    )

                if delete_menu:
                    print("➡️ '삭제' 메뉴 클릭")
                    driver.execute_script("arguments[0].click();", delete_menu[0])
                    time.sleep(2)

                    # 확인 모달의 '삭제' 버튼 클릭
                    # 모달의 빨간 삭제 버튼은 보통 btn-danger 또는 btn-primary 클래스
                    confirm_btns = driver.find_elements(
                        By.XPATH,
                        "//button[contains(@class, 'btn-danger') and contains(., '삭제')]"
                    )
                    if not confirm_btns:
                        # 대안: dialog 내부의 삭제 버튼
                        confirm_btns = driver.find_elements(
                            By.XPATH,
                            "//dialog//button[contains(., '삭제')] | //div[@role='dialog']//button[contains(., '삭제')]"
                        )
                    if not confirm_btns:
                        # 최후 폴백
                        confirm_btns = driver.find_elements(
                            By.XPATH,
                            "//button[.//div[text()='삭제']]"
                        )
                    if confirm_btns:
                        print("➡️ '삭제(확인)' 클릭")
                        driver.execute_script("arguments[0].click();", confirm_btns[-1])
                        time.sleep(2)
                        lib_delete_count += 1
                    else:
                        print("⚠️ 확인 모달의 삭제 버튼을 찾지 못했습니다. Esc로 닫기 시도.")
                        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        time.sleep(1)
                        break
                else:
                    print("⚠️ 드롭다운에서 '삭제' 메뉴를 찾지 못했습니다. Esc로 닫기.")
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    time.sleep(1)
                    break

            # ===== (B) 사이드바 프로젝트 개별 삭제 루프 =====
            # 사이드바의 채팅 기록에서 대화 옵션(⋯) → 삭제
            while True:
                option_btns = driver.find_elements(By.CSS_SELECTOR, "button[data-trailing-button]")
                if not option_btns:
                    print("➡️ 삭제할 프로젝트가 더 이상 없습니다.")
                    break

                print("➡️ '프로젝트 옵션 열기' 클릭")
                driver.execute_script("arguments[0].click();", option_btns[0])
                time.sleep(1)

                # '프로젝트 삭제' 텍스트를 가진 메뉴 항목 클릭
                del_proj_menus = driver.find_elements(
                    By.XPATH,
                    "//*[contains(text(), '프로젝트 삭제') or contains(text(), '삭제')]"
                )
                # 드롭다운 메뉴 아이템 중 '삭제' 텍스트가 있는 것 우선
                del_menu_item = None
                for item in del_proj_menus:
                    txt = item.text.strip()
                    if '삭제' in txt:
                        del_menu_item = item
                        break

                if del_menu_item:
                    print("➡️ '프로젝트 삭제' 클릭")
                    driver.execute_script("arguments[0].click();", del_menu_item)
                    time.sleep(3)

                    # 확인 창의 '삭제' 클릭 (모달 내 버튼)
                    confirm_btns = driver.find_elements(
                        By.XPATH,
                        "//button[contains(@class, 'btn-danger')] | //dialog//button[contains(., '삭제')] | //div[@role='dialog']//button[contains(., '삭제')]"
                    )
                    if not confirm_btns:
                        confirm_btns = driver.find_elements(
                            By.XPATH,
                            "//button[.//div[text()='삭제']]"
                        )
                    if confirm_btns:
                        print("➡️ '삭제(확인)' 클릭")
                        driver.execute_script("arguments[0].click();", confirm_btns[-1])
                        time.sleep(3)
                    else:
                        print("⚠️ 확인 버튼을 못 찾음, Esc로 닫기")
                        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        time.sleep(1)
                        break
                else:
                    # 메뉴가 안 뜨면 Esc 후 무한 루프 방지
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    time.sleep(1)
                    break



            # ===== (D) 설정 → 보안 → 모두 로그아웃 =====
            print("➡️ 설정 > 보안 페이지로 이동")
            driver.get("https://chatgpt.com/#settings/Security")
            time.sleep(4)  # 설정 모달 로딩 대기

            # '모두 로그아웃' 버튼 클릭
            print("➡️ '모두 로그아웃' 버튼 클릭")
            logout_all_btn = driver.find_elements(
                By.CSS_SELECTOR, "[data-testid='logout-all-button']"
            )
            if not logout_all_btn:
                logout_all_btn = driver.find_elements(
                    By.XPATH,
                    "//button[contains(., '모두 로그아웃')]"
                )
            if logout_all_btn:
                driver.execute_script("arguments[0].click();", logout_all_btn[0])
                time.sleep(3)  # 확인 팝업 대기

                # '모든 기기에서 로그아웃' 확인 버튼 클릭
                print("➡️ '모든 기기에서 로그아웃' 확인 클릭")
                confirm_logout = driver.find_elements(
                    By.XPATH,
                    "//button[contains(@class, 'btn-danger') and contains(., '모든 기기에서 로그아웃')]"
                )
                if not confirm_logout:
                    confirm_logout = driver.find_elements(
                        By.XPATH,
                        "//dialog//button[contains(., '모든 기기에서 로그아웃')] | //div[@role='dialog']//button[contains(., '모든 기기에서 로그아웃')]"
                    )
                if not confirm_logout:
                    confirm_logout = driver.find_elements(
                        By.XPATH,
                        "//button[.//div[contains(text(), '모든 기기에서 로그아웃')]]"
                    )
                if confirm_logout:
                    driver.execute_script("arguments[0].click();", confirm_logout[-1])
                    time.sleep(5)  # 로그아웃 처리 및 리디렉션 대기
                    print("✅ 모든 기기에서 로그아웃 완료")
                else:
                    print("⚠️ '모든 기기에서 로그아웃' 확인 버튼을 찾지 못했습니다.")
            else:
                print("⚠️ '모두 로그아웃' 버튼을 찾지 못했습니다.")

        except Exception as e:
            print(f"⚠️ 초기화 단계 자동 클릭 중 오류 발생: {e}")

        # 로그아웃 후 초기 화면 복귀 확인
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='login-button']"))
            )
            print("🟢 로그인 화면 복귀 확인!")
        except:
            print("⚠️ 로그인 화면 복귀를 자동 감지하지 못했습니다. (이미 로그아웃 되었을 수 있습니다)")

        print(f"✅ {target_email} 계정 초기화 완료!")

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
    
    for num in target_numbers:
        target_email = f"gpt{num}@ablearn.kr"
        
        # 매 계정마다 브라우저를 새로 열어 쿠키/세션을 완전 초기화
        # undetected_chromedriver는 ChromeOptions 재사용 불가 → 매번 새로 생성
        options = uc.ChromeOptions()
        driver = uc.Chrome(options=options, version_main=147)
        driver.set_window_size(1920, 1080)  # 넓은 뷰포트 — 체크박스 렌더링에 필요
        
        login_and_reset(driver, target_email)
        
        driver.quit()
        time.sleep(2) # 다음 계정으로 넘어가기 전 잠시 대기
            
    print("\n🎉 모든 계정의 작업이 끝났습니다!")

if __name__ == "__main__":
    main()
