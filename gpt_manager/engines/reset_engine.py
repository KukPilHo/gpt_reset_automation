"""
GPT 계정 초기화 엔진
기존 reset_gpt_accounts_parallel.py의 핵심 로직을 최소 변경으로 래핑합니다.

변경된 부분:
- log() → log_callback 콜백 기반
- .env → config dict 파라미터
- main() → run_reset() 함수
- process_account() 내부 로직은 변경 없음
"""
import os
import re
import time
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

from utils.imap_helper import get_openai_code


def process_account(num, config, log_callback, stop_event=None):
    """하나의 계정에 대한 전체 초기화 프로세스 (독립 스레드에서 실행)
    
    ※ 기존 reset_gpt_accounts_parallel.py의 process_account()와 동일한 로직.
       log()를 로컬 함수로 래핑하여 콜백을 사용합니다.
    """
    # --- 콜백 래핑: 기존 log(tag, msg) 호출을 그대로 유지 ---
    def log(tag, msg):
        if log_callback:
            log_callback(tag, msg)

    # --- 설정값을 로컬 변수로 할당: 기존 전역 변수 참조를 그대로 유지 ---
    MASTER_EMAIL = config["master_email"]
    APP_PASSWORD = config["app_password"]
    COMMON_PASSWORD = config["common_password"]

    target_email = f"gpt{num}@ablearn.kr"
    tag = f"gpt{num}"

    # 독립 Chrome 프로필 디렉토리 생성
    profile_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_gpt{num}")

    log(tag, "=========================================================")
    log(tag, f"🚀 작업 시작: {target_email}")

    for overall_attempt in range(3):
        if stop_event and stop_event.is_set():
            return {"email": target_email, "status": "STOPPED", "reason": "사용자 중단"}

        if overall_attempt > 0:
            log(tag, f"🔄 브라우저 재시작 및 전체 과정 재시도 중... (시도 {overall_attempt + 1}/3)")

        driver = None
        try:
            # 독립 Chrome 인스턴스 생성
            options = uc.ChromeOptions()
            options.add_argument(f"--user-data-dir={profile_dir}")
            driver = uc.Chrome(options=options)
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
                code = get_openai_code(MASTER_EMAIL, APP_PASSWORD, target_email, login_timestamp=login_request_time, log_callback=log_callback)
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

            # --- (B-0) GPT 사이드바에서 숨기기 ---
            log(tag, "➡️ GPT 사이드바에서 숨기기")
            driver.get("https://chatgpt.com")
            time.sleep(4)

            gpt_hidden_count = 0
            for _ in range(50):
                gpt_btn_exists = driver.execute_script("""
                    const items = document.querySelectorAll('a[data-sidebar-item][href*="/g/g-"]');
                    for (const item of items) {
                        if (!item.href.includes('/project')) {
                            const btn = item.querySelector('button[data-trailing-button]');
                            if (btn) return true;
                        }
                    }
                    return false;
                """)

                if not gpt_btn_exists:
                    break

                driver.execute_script("""
                    const items = document.querySelectorAll('a[data-sidebar-item][href*="/g/g-"]');
                    for (const item of items) {
                        if (!item.href.includes('/project')) {
                            const btn = item.querySelector('button[data-trailing-button]');
                            if (btn) { btn.click(); return; }
                        }
                    }
                """)
                time.sleep(1.5)

                hide_items = driver.find_elements(By.XPATH, "//*[contains(text(), '사이드바에서 숨기기')]")
                if hide_items:
                    driver.execute_script("arguments[0].click();", hide_items[-1])
                    time.sleep(2)
                    gpt_hidden_count += 1
                else:
                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                    time.sleep(1)

            log(tag, f"✅ GPT 사이드바 숨기기 완료 ({gpt_hidden_count}개)")

            # --- (B) 프로젝트 삭제 (2회 체크) ---
            log(tag, "➡️ 프로젝트 삭제 시작")

            for check_round in range(2):
                if check_round > 0:
                    log(tag, "🔄 프로젝트 삭제 재확인 중...")
                    driver.get("https://chatgpt.com")
                    time.sleep(4)

                deleted_in_round = 0
                for _ in range(200):
                    project_btn_count = driver.execute_script("""
                        return document.querySelectorAll(
                            'a[data-sidebar-item][href*="/project"] button[data-trailing-button]'
                        ).length;
                    """)

                    if project_btn_count == 0:
                        break

                    driver.execute_script("""
                        const btn = document.querySelector(
                            'a[data-sidebar-item][href*="/project"] button[data-trailing-button]'
                        );
                        if (btn) btn.click();
                    """)
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
                            deleted_in_round += 1
                            break

                    if not clicked:
                        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        break

                log(tag, f"  ↳ {check_round + 1}차: {deleted_in_round}개 삭제")

            log(tag, "✅ 프로젝트 삭제 완료")

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


def run_reset(target_numbers, max_workers, config, log_callback, stop_event=None):
    """여러 계정의 초기화를 병렬로 실행합니다.
    
    기존 main()의 ThreadPoolExecutor 로직과 동일합니다.
    """
    log_callback("시스템", f"총 {len(target_numbers)}개의 계정, 최대 {max_workers}개 동시 실행: {target_numbers}")

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for num in target_numbers:
            if stop_event and stop_event.is_set():
                break
            future = executor.submit(process_account, num, config, log_callback, stop_event)
            futures[future] = num

        for future in as_completed(futures):
            num = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({"email": f"gpt{num}@ablearn.kr", "status": "FAIL", "reason": str(e)})

    # 결과 요약 로그
    ok_count = sum(1 for r in results if r["status"] == "OK")
    fail_count = sum(1 for r in results if r["status"] != "OK")
    log_callback("시스템", f"📊 완료 — 성공: {ok_count}개 | 실패: {fail_count}개")

    return results
