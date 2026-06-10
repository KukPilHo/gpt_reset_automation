"""
프로젝트 삭제 진단 스크립트 (단독 실행)
============================================
계정 1개만 로그인하여 '프로젝트 삭제' 단계만 집중 진단합니다.
본 코드(reset_engine.py)는 건드리지 않고, 원인 파악용 데이터만 수집합니다.

검증 항목:
  1. 사이드바 셀렉터로 잡히는 프로젝트 수  (현재 로직이 보는 값)
  2. 사이드바 스크롤 / '더 보기' 펼친 뒤의 프로젝트 수  (lazy loading 여부)
  3. 삭제 메뉴를 열었을 때의 실제 메뉴 항목들
  4. 확인 모달의 버튼 구조
  5. 삭제 1건 시도 후 실제로 개수가 줄었는지

사용법:
  cd gpt_manager
  python diagnose_project_delete.py 5          # gpt5@ablearn.kr 진단 (삭제 시도 X, 조사만)
  python diagnose_project_delete.py 5 --delete  # 실제 삭제까지 1건 시도하며 검증

결과:
  diagnose_out/ 폴더에 스크린샷과 DOM 스냅샷(html/json)이 저장됩니다.
"""
import os
import sys
import time
import json
import shutil
import tempfile
import argparse
from datetime import datetime, timezone, timedelta

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.config import load_config
from utils.imap_helper import get_openai_code

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagnose_out")


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def save_artifact(driver, name):
    """스크린샷 + 현재 DOM 일부를 파일로 저장"""
    os.makedirs(OUT_DIR, exist_ok=True)
    try:
        driver.save_screenshot(os.path.join(OUT_DIR, f"{name}.png"))
    except Exception as e:
        log(f"  (스크린샷 저장 실패: {e})")


def dump_sidebar(driver, label):
    """문서 전체에서 사이드바 후보를 모두 찾아 outerHTML 통째로 저장 — 실제 구조 확정용"""
    os.makedirs(OUT_DIR, exist_ok=True)

    info = driver.execute_script(r"""
        const result = {all_anchors: [], data_sidebar_items: [], trailing_buttons: 0, navs: 0, asides: 0};

        // (1) 문서 전체 모든 a 태그 (nav 한정 X)
        document.querySelectorAll('a').forEach(a => {
            const href = a.getAttribute('href');
            result.all_anchors.push({
                text: (a.textContent || '').trim().slice(0, 40),
                href: href,
                dataAttrs: Object.fromEntries(
                    [...a.attributes].filter(at => at.name.startsWith('data-')).map(at => [at.name, at.value])
                ),
                hasTrailingBtn: !!a.querySelector('button[data-trailing-button]'),
            });
        });

        // (2) data-sidebar-item 가진 모든 요소 (a가 아닐 수도 있으므로)
        document.querySelectorAll('[data-sidebar-item]').forEach(el => {
            result.data_sidebar_items.push({
                tag: el.tagName,
                text: (el.textContent || '').trim().slice(0, 40),
                href: el.getAttribute('href'),
                dataAttrs: Object.fromEntries(
                    [...el.attributes].filter(at => at.name.startsWith('data-')).map(at => [at.name, at.value])
                ),
            });
        });

        result.trailing_buttons = document.querySelectorAll('button[data-trailing-button]').length;
        result.navs = document.querySelectorAll('nav').length;
        result.asides = document.querySelectorAll('aside').length;
        return result;
    """)

    log(f"── [{label}] 문서 전체 링크/사이드바 항목 덤프 ──")
    log(f"   nav 요소 {info['navs']}개, aside 요소 {info['asides']}개, trailing-button {info['trailing_buttons']}개")
    log(f"   문서 전체 a 링크 {len(info['all_anchors'])}개:")
    for it in info['all_anchors']:
        flag = "✔btn" if it['hasTrailingBtn'] else "    "
        dattrs = " ".join(f"{k}={v}" for k, v in it['dataAttrs'].items()) or "-"
        log(f"      [{flag}] '{it['text']:<38}' href={it['href']}  | {dattrs}")
    log(f"   data-sidebar-item 요소 {len(info['data_sidebar_items'])}개:")
    for it in info['data_sidebar_items']:
        log(f"      <{it['tag']}> '{it['text']:<38}' href={it['href']}")

    with open(os.path.join(OUT_DIR, f"sidebar_{label}.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    # ★ 모든 nav / aside 의 outerHTML 을 통째로 파일로 저장 (구조 직접 분석용)
    htmls = driver.execute_script(r"""
        const out = [];
        document.querySelectorAll('nav, aside').forEach((el, i) => {
            out.push('<!-- ===== ' + el.tagName + ' #' + i +
                     '  class=' + (el.className||'').toString() + ' ===== -->\n' + el.outerHTML);
        });
        return out.join('\n\n');
    """)
    html_path = os.path.join(OUT_DIR, f"sidebar_{label}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(htmls or "(nav/aside 없음)")
    log(f"   📄 사이드바 HTML 저장: {html_path}")

    # 백업: body 전체 HTML (nav/aside 밖에 있을 경우 대비)
    body_html = driver.execute_script("return document.body.outerHTML;")
    body_path = os.path.join(OUT_DIR, f"body_{label}.html")
    with open(body_path, "w", encoding="utf-8") as f:
        f.write(body_html or "")
    log(f"   📄 body 전체 HTML 저장: {body_path}")
    return info


def dump_projects(driver, label):
    """현재 DOM에서 프로젝트 관련 요소들을 조사하여 출력 + 저장"""
    info = driver.execute_script(r"""
        const result = {};

        // (1) 현재 reset_engine 이 사용하는 셀렉터
        const current = document.querySelectorAll(
            'a[data-sidebar-item][href*="/project"] button[data-trailing-button]'
        );
        result.current_selector_count = current.length;

        // (2) project 링크 전체 (trailing-button 유무와 무관하게)
        const allProjectLinks = document.querySelectorAll('a[href*="/project"]');
        result.all_project_links = allProjectLinks.length;

        // (3) project 링크들의 href / 텍스트 목록
        result.project_items = [];
        allProjectLinks.forEach(a => {
            result.project_items.push({
                href: a.getAttribute('href'),
                text: (a.textContent || '').trim().slice(0, 40),
                hasTrailingBtn: !!a.querySelector('button[data-trailing-button]'),
                isSidebarItem: a.hasAttribute('data-sidebar-item'),
            });
        });

        // (4) '더 보기' / 'See more' 류 버튼 탐색
        result.see_more_candidates = [];
        document.querySelectorAll('button, a, div[role="button"]').forEach(el => {
            const t = (el.textContent || '').trim();
            if (t && t.length < 20 && (t.includes('더 보기') || t.includes('더보기')
                || t.toLowerCase().includes('see more') || t.includes('모두 보기')
                || t.includes('전체') )) {
                result.see_more_candidates.push(t);
            }
        });

        // (5) 사이드바 스크롤 컨테이너 후보
        result.scroll_containers = [];
        document.querySelectorAll('nav, aside, [class*="scroll"], [class*="sidebar"]').forEach(el => {
            if (el.scrollHeight > el.clientHeight + 20) {
                result.scroll_containers.push({
                    tag: el.tagName,
                    cls: (el.className || '').toString().slice(0, 60),
                    scrollHeight: el.scrollHeight,
                    clientHeight: el.clientHeight,
                });
            }
        });

        return result;
    """)

    log(f"── [{label}] 프로젝트 조사 ──")
    log(f"   현재 셀렉터가 보는 프로젝트 수 (reset_engine 기준): {info['current_selector_count']}")
    log(f"   /project href 링크 전체 수                        : {info['all_project_links']}")
    if info['see_more_candidates']:
        log(f"   ⚠️ '더 보기'류 버튼 후보 발견: {info['see_more_candidates']}")
    if info['scroll_containers']:
        log(f"   스크롤 가능한 컨테이너 {len(info['scroll_containers'])}개 (lazy load 가능성)")
        for sc in info['scroll_containers'][:5]:
            log(f"      - {sc['tag']}.{sc['cls']}  ({sc['clientHeight']}→{sc['scrollHeight']})")
    log(f"   프로젝트 항목 목록:")
    for it in info['project_items']:
        flag = "✔btn" if it['hasTrailingBtn'] else "✘btn"
        log(f"      [{flag}] {it['text']:<40} {it['href']}")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, f"projects_{label}.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    return info


def scroll_sidebar_to_load_all(driver):
    """사이드바 스크롤 컨테이너를 끝까지 내려서 lazy load 항목을 모두 로드 시도"""
    log("── 사이드바 스크롤하며 추가 로딩 시도 ──")
    prev = -1
    for i in range(15):
        cnt = driver.execute_script("return document.querySelectorAll('a[href*=\"/project\"]').length;")
        log(f"   스크롤 {i+1}회 → /project 링크 {cnt}개")
        if cnt == prev:
            log("   더 이상 늘지 않음 (로딩 완료로 판단)")
            break
        prev = cnt
        driver.execute_script(r"""
            const cands = document.querySelectorAll('nav, aside, [class*="scroll"], [class*="sidebar"]');
            cands.forEach(el => {
                if (el.scrollHeight > el.clientHeight + 20) {
                    el.scrollTop = el.scrollHeight;
                }
            });
        """)
        time.sleep(1.2)


def inspect_delete_menu(driver):
    """첫 번째 프로젝트의 메뉴를 열고 메뉴 항목들을 덤프"""
    log("── 첫 프로젝트 삭제 메뉴 조사 ──")
    opened = driver.execute_script(r"""
        const a = document.querySelector('a[data-sidebar-item][href*="/project"]');
        if (!a) return null;
        const btn = a.querySelector('button[data-trailing-button]');
        if (!btn) return 'no-trailing-button';
        btn.click();
        return 'clicked';
    """)
    log(f"   메뉴 트리거: {opened}")
    if opened != 'clicked':
        return
    time.sleep(1.5)

    menu = driver.execute_script(r"""
        const items = [];
        document.querySelectorAll('[role="menuitem"], [role="menu"] *').forEach(el => {
            const t = (el.textContent || '').trim();
            if (t && t.length < 30) items.push({role: el.getAttribute('role'), text: t});
        });
        return items;
    """)
    log("   메뉴 항목들:")
    seen = set()
    for m in menu:
        key = m['text']
        if key in seen:
            continue
        seen.add(key)
        log(f"      role={m['role']}  text='{m['text']}'")
    save_artifact(driver, "delete_menu_open")

    # 메뉴 닫기
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass
    time.sleep(1)


def inspect_confirm_dialog(driver):
    """삭제를 눌러 확인 모달을 띄우고, 모달 버튼 구조를 덤프 (실제 확인은 누르지 않음)"""
    log("── 확인 모달 구조 조사 (실제 삭제 확인은 누르지 않음) ──")
    # 메뉴 다시 열기
    driver.execute_script(r"""
        const a = document.querySelector('a[data-sidebar-item][href*="/project"]');
        if (a) { const btn = a.querySelector('button[data-trailing-button]'); if (btn) btn.click(); }
    """)
    time.sleep(1.5)

    # 메뉴에서 '삭제' 항목 클릭
    clicked = driver.execute_script(r"""
        const items = document.querySelectorAll('[role="menuitem"]');
        for (const it of items) {
            if ((it.textContent || '').includes('삭제')) { it.click(); return (it.textContent||'').trim(); }
        }
        return null;
    """)
    log(f"   메뉴 '삭제' 클릭: {clicked}")
    if not clicked:
        log("   ⚠️ 메뉴에서 '삭제' 항목을 못 찾음")
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass
        return

    time.sleep(2)
    save_artifact(driver, "confirm_dialog")

    dialog = driver.execute_script(r"""
        const result = {dialogs: 0, buttons: []};
        const dlgs = document.querySelectorAll('dialog, [role="dialog"], [role="alertdialog"]');
        result.dialogs = dlgs.length;
        const scope = dlgs.length ? dlgs[dlgs.length-1] : document;
        scope.querySelectorAll('button').forEach(b => {
            result.buttons.push({
                text: (b.textContent || '').trim().slice(0, 30),
                cls: (b.className || '').toString().slice(0, 60),
                testid: b.getAttribute('data-testid'),
            });
        });
        return result;
    """)
    log(f"   모달 개수: {dialog['dialogs']}")
    log("   모달 내 버튼들:")
    for b in dialog['buttons']:
        log(f"      text='{b['text']}'  testid={b['testid']}  cls='{b['cls']}'")

    with open(os.path.join(OUT_DIR, "confirm_dialog.json"), "w", encoding="utf-8") as f:
        json.dump(dialog, f, ensure_ascii=False, indent=2)

    # 모달 닫기 (취소)
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception:
        pass
    time.sleep(1)
    return dialog


def attempt_one_delete(driver):
    """실제로 프로젝트 1건을 삭제 시도하고, 전후 개수를 비교하여 성공 여부 검증"""
    log("── 실제 삭제 1건 시도 + 검증 ──")
    before = driver.execute_script("return document.querySelectorAll('a[href*=\"/project\"]').length;")
    log(f"   삭제 전 /project 링크 수: {before}")

    driver.execute_script(r"""
        const a = document.querySelector('a[data-sidebar-item][href*="/project"]');
        if (a) { const btn = a.querySelector('button[data-trailing-button]'); if (btn) btn.click(); }
    """)
    time.sleep(1.5)
    driver.execute_script(r"""
        const items = document.querySelectorAll('[role="menuitem"]');
        for (const it of items) {
            if ((it.textContent || '').includes('삭제')) { it.click(); return; }
        }
    """)
    time.sleep(2)

    # 확인 버튼: 여러 후보를 명시적으로 대기
    confirmed = False
    for _ in range(10):
        cfm = driver.find_elements(By.CSS_SELECTOR, "[role='dialog'] button.btn-danger, [role='alertdialog'] button.btn-danger")
        if not cfm:
            cfm = driver.find_elements(By.XPATH, "//*[@role='dialog' or @role='alertdialog']//button[contains(., '삭제')]")
        if cfm:
            driver.execute_script("arguments[0].click();", cfm[-1])
            confirmed = True
            log(f"   확인 버튼 클릭: '{cfm[-1].text.strip()}'")
            break
        time.sleep(0.5)

    if not confirmed:
        log("   ❌ 확인 버튼을 못 찾음 — 현재 로직이 여기서 '성공'으로 잘못 카운트함")
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass
        return

    # 삭제 후 개수 변화 대기
    time.sleep(3)
    after = driver.execute_script("return document.querySelectorAll('a[href*=\"/project\"]').length;")
    log(f"   삭제 후 /project 링크 수: {after}")
    if after < before:
        log(f"   ✅ 실제로 {before - after}개 줄어듦 (삭제 동작 정상)")
    else:
        log(f"   ❌ 개수가 줄지 않음 — 확인은 눌렀으나 삭제 미반영 (DOM 갱신 지연 또는 실패)")
    save_artifact(driver, "after_delete")


def login(driver, target_email, config):
    log(f"🚀 로그인 시작: {target_email}")
    driver.get("https://chatgpt.com")

    login_btn = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='login-button']"))
    )
    login_btn.click()

    login_request_time = datetime.now(timezone.utc) - timedelta(seconds=5)
    email_input = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email']"))
    )
    email_input.send_keys(target_email)
    email_input.send_keys(Keys.RETURN)

    found_pw = found_code = False
    for _ in range(12):
        if driver.find_elements(By.CSS_SELECTOR, "input[type='password']"):
            found_pw = True
            break
        if driver.find_elements(By.CSS_SELECTOR, "input[inputmode='numeric'], input[name='code']") or "code" in driver.current_url.lower():
            found_code = True
            break
        time.sleep(1)

    if found_pw:
        log("🔑 비밀번호 입력")
        pw = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        pw.send_keys(config["common_password"])
        pw.send_keys(Keys.RETURN)
        time.sleep(3)
        if driver.find_elements(By.CSS_SELECTOR, "input[inputmode='numeric'], input[name='code']") or "code" in driver.current_url.lower():
            found_code = True

    if found_code:
        log("📩 인증 코드 필요")
        code = get_openai_code(config["master_email"], config["app_password"], target_email,
                               login_timestamp=login_request_time, log_callback=lambda t, m: log(m))
        if not code:
            raise RuntimeError("인증 코드 수신 실패")
        log(f"✅ 인증 코드: {code}")
        ci = driver.find_elements(By.CSS_SELECTOR, "input[inputmode='numeric'], input[name='code']")
        if ci:
            ci[0].send_keys(code)
            ci[0].send_keys(Keys.RETURN)

    log("⏳ 로그인 완료 대기...")
    for _ in range(30):
        if driver.find_elements(By.ID, "prompt-textarea"):
            log("🟢 로그인 성공!")
            return True
        account_btns = driver.find_elements(By.CSS_SELECTOR, "fieldset > button")
        if len(account_btns) >= 2:
            log("➡️ 계정 선택 — 첫 번째")
            driver.execute_script("arguments[0].click();", account_btns[0])
            time.sleep(3)
            continue
        time.sleep(1)

    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, "prompt-textarea")))
    log("🟢 로그인 성공!")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("num", type=int, help="계정 번호 (예: 5 → gpt5@ablearn.kr)")
    parser.add_argument("--delete", action="store_true", help="실제 삭제 1건까지 시도하며 검증")
    args = parser.parse_args()

    config = load_config()
    if not (config.get("master_email") and config.get("app_password") and config.get("common_password")):
        log("❌ config.json 설정이 비어 있습니다. (gpt_manager 앱에서 설정 먼저)")
        sys.exit(1)

    target_email = f"gpt{args.num}@ablearn.kr"
    profile_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_diag_gpt{args.num}")

    driver = None
    try:
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={profile_dir}")
        driver = uc.Chrome(options=options)
        driver.set_window_size(1920, 1080)

        login(driver, target_email, config)

        # 메인 화면으로 이동 (사이드바 로딩) — 사이드바 hydration 충분히 대기
        driver.get("https://chatgpt.com")
        time.sleep(10)

        # 0) 사이드바 전체 링크 덤프 — 새 URL 구조 파악 (최우선)
        dump_sidebar(driver, "00_sidebar")

        # 1) 현재 로직이 보는 상태
        dump_projects(driver, "01_initial")

        # 2) 스크롤로 lazy load 항목 펼친 뒤 다시
        scroll_sidebar_to_load_all(driver)
        dump_projects(driver, "02_after_scroll")
        save_artifact(driver, "sidebar_after_scroll")

        # 3) 메뉴 / 모달 구조 조사
        inspect_delete_menu(driver)
        inspect_confirm_dialog(driver)

        # 4) (옵션) 실제 삭제 1건 검증
        if args.delete:
            attempt_one_delete(driver)
            dump_projects(driver, "03_after_one_delete")

        log("")
        log("=========================================================")
        log(f"진단 완료. 결과물: {OUT_DIR}")
        log("창을 닫으려면 Enter...")
        input()

    except Exception as e:
        log(f"❌ 에러: {e}")
        if driver:
            save_artifact(driver, "error_state")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        try:
            if os.path.exists(profile_dir):
                shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
