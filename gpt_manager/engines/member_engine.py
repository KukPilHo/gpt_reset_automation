"""
Google Groups 멤버 추가 엔진 (병렬 처리 지원)
"""
import time
import asyncio

def run_add_members(tasks, log_callback, login_event=None, stop_event=None):
    """Google Groups에 멤버를 병렬(다중 탭)로 추가하는 동기 래퍼 함수입니다.
    
    앱 서버의 구조를 유지하기 위해, 내부에 새로운 이벤트 루프를 생성하여
    비동기 처리(async_playwright)를 실행합니다.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        results = loop.run_until_complete(run_add_members_async(tasks, log_callback, login_event, stop_event))
        return results
    finally:
        loop.close()

async def check_email_exists(page, email: str) -> bool:
    """현재 멤버 목록 페이지에서 해당 이메일이 이미 존재하는지 확인합니다.
    ds:12 스크립트 데이터 파싱, HTML 포함 여부 및 텍스트 검사를 병행합니다.
    """
    email_lower = email.strip().lower()
    js_code = """
    (email) => {
        const emailLower = email.toLowerCase().trim();
        try {
            const scripts = document.querySelectorAll('script.ds\\\\:12, script[class="ds:12"]');
            for (const script of scripts) {
                const text = script.textContent || '';
                const emailRegex = /[\\\\w._%+-]+@[\\\\w.-]+\\\\.[a-zA-Z]{2,}/g;
                const matches = text.match(emailRegex);
                if (matches) {
                    for (const match of matches) {
                        if (match.toLowerCase() === emailLower) {
                            return true;
                        }
                    }
                }
            }
        } catch(e) {}
        
        try {
            const bodyHTML = document.body.innerHTML;
            if (bodyHTML.toLowerCase().includes('"' + emailLower + '"') ||
                bodyHTML.toLowerCase().includes('>' + emailLower + '<') ||
                bodyHTML.toLowerCase().includes(',' + emailLower + ',')) {
                return true;
            }
        } catch(e) {}

        try {
            const bodyText = document.body.innerText;
            if (bodyText.toLowerCase().includes(emailLower)) {
                return true;
            }
        } catch(e) {}
        
        return false;
    }
    """
    try:
        return await page.evaluate(js_code, email_lower)
    except Exception:
        return False

async def process_single_job_async(index, task, context, stop_event, log):
    """개별 이메일에 대해 회원 추가 탭을 열고 자동 등록 프로세스를 진행합니다."""
    target_email = task["email"].strip()
    gpt_id_raw = task["gpt"].strip()
    if not target_email or not gpt_id_raw:
        return None

    gpt_id = gpt_id_raw.split('@')[0]
    url = f"https://groups.google.com/a/ablearn.kr/g/{gpt_id}/members"
    
    page = await context.new_page()
    try:
        await page.goto(url)
        await page.wait_for_load_state("networkidle")

        # 1. 사전 체크: 추가하려는 이메일이 이미 멤버 목록에 있는지 확인
        if await check_email_exists(page, target_email):
            log(f"🔵 이미 추가됨: {target_email} → {gpt_id}")
            return {"email": target_email, "gpt": gpt_id, "status": "ALREADY_EXISTS"}

        if stop_event and stop_event.is_set():
            return {"email": target_email, "gpt": gpt_id, "status": "FAIL", "reason": "사용자 중단"}

        # 2. '회원 추가' 버튼 클릭
        add_btn = page.locator("text=회원 추가").first
        if await add_btn.count() == 0:
            add_btn = page.get_by_label("회원 추가")
        await add_btn.wait_for(state="visible", timeout=10000)
        await add_btn.click()
        await asyncio.sleep(1.5)

        # 3. 이메일 입력
        member_input = page.get_by_label("그룹 멤버")
        await member_input.wait_for(state="visible", timeout=5000)
        await member_input.click()
        await member_input.fill(target_email)
        await asyncio.sleep(1)
        await member_input.click()
        await member_input.press("Tab")
        await asyncio.sleep(1)

        if stop_event and stop_event.is_set():
            return {"email": target_email, "gpt": gpt_id, "status": "FAIL", "reason": "사용자 중단"}

        # 4. 하단 '회원 추가' 제출 버튼 클릭
        confirm_add_btn = page.get_by_role("button", name="회원 추가").last
        await confirm_add_btn.wait_for(state="visible", timeout=5000)
        await confirm_add_btn.click()

        # 5. "회원이 업데이트되었습니다" 모달 대기 (유일한 성공 조건)
        try:
            success_title = page.locator("text=회원이 업데이트되었습니다")
            await success_title.wait_for(state="visible", timeout=6000)

            ok_btn = page.get_by_role("button", name="확인")
            if await ok_btn.is_visible():
                await ok_btn.click()
                await asyncio.sleep(0.5)

            log(f"✅ 성공: {target_email} → {gpt_id}")
            return {"email": target_email, "gpt": gpt_id, "status": "OK"}
        except Exception:
            err_text = "성공 팝업(회원이 업데이트되었습니다)을 찾지 못했습니다."
            try:
                # 팝업이 안 뜬 경우, 다른 에러 메시지 추출
                alert_box = page.locator("[role='alert'], .m2-snackbar")
                if await alert_box.count() > 0 and await alert_box.first.is_visible():
                    err_text = await alert_box.first.inner_text()
            except:
                pass

            # 에러 발생 후 사후 체크: 에러가 났지만 실제로는 추가가 완료된 경우
            if await check_email_exists(page, target_email):
                log(f"🔵 사후 확인: {target_email}이(가) 에러 후에도 멤버 목록에 존재합니다 → 성공 처리")
                return {"email": target_email, "gpt": gpt_id, "status": "ALREADY_EXISTS"}

            log(f"❌ 실패 ({target_email}): {err_text}")
            return {"email": target_email, "gpt": gpt_id, "status": "FAIL", "reason": err_text}
            
    except Exception as e:
        # 최종 예외 발생 시에도 사후 체크 진행
        try:
            if await check_email_exists(page, target_email):
                log(f"🔵 사후 확인: {target_email}이(가) 예외 발생 후에도 멤버 목록에 존재합니다 → 성공 처리")
                return {"email": target_email, "gpt": gpt_id, "status": "ALREADY_EXISTS"}
        except:
            pass
        log(f"❌ 실패 ({target_email}): {e}")
        return {"email": target_email, "gpt": gpt_id, "status": "FAIL", "reason": str(e)}
    finally:
        await page.close()

async def run_add_members_async(tasks, log_callback, login_event=None, stop_event=None):
    def log(msg):
        log_callback("멤버추가", msg)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log("❌ Playwright가 설치되어 있지 않습니다. 'pip3 install playwright && playwright install chromium' 을 실행해주세요.")
        return [{"status": "FAIL", "reason": "Playwright 미설치"}]

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False, channel="chrome")
        except Exception as e:
            log(f"❌ 크롬 브라우저를 찾을 수 없습니다. 구글 크롬이 설치되어 있는지 확인해주세요. ({e})")
            return [{"status": "FAIL", "reason": "크롬 미설치"}]
        context = await browser.new_context()
        
        # 메인 탭 생성
        main_page = await context.new_page()

        # 구글 로그인 대기
        await main_page.goto("https://accounts.google.com/")
        log("🟢 브라우저가 열렸습니다.")
        log("⚠️ 반드시 회사 계정(ablearn.kr)으로 Chrome에 로그인해주세요!")
        log("⚠️ Google Workspace 관리자 계정이어야 멤버 추가가 가능합니다.")
        log("🟢 로그인이 완전히 끝난 후 아래 '로그인 완료' 버튼을 클릭해주세요.")

        # 로그인 이벤트 대기 (비동기 루프)
        if login_event:
            while not login_event.is_set():
                if stop_event and stop_event.is_set():
                    log("🛑 사용자에 의해 작업이 중단되었습니다.")
                    await browser.close()
                    return []
                await asyncio.sleep(0.5)
        
        log("✅ 로그인 확인 — 자동 추가를 시작합니다.")

        # 최대 동시 실행할 탭 개수 (chrome_extension MAX_CONCURRENT = 6 에 맞춰 상향)
        MAX_CONCURRENT_TABS = 6
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TABS)

        accumulated_results = []
        current_tasks = tasks[:]
        prev_fail_count = float('inf')
        retry_round = 0

        while True:
            if stop_event and stop_event.is_set():
                break
            retry_round += 1

            if retry_round > 1:
                log(f"🔄 자동 재시도 {retry_round - 1}회차 시작 (실패 {len(current_tasks)}건)")
                for _ in range(20):
                    if stop_event and stop_event.is_set():
                        break
                    await asyncio.sleep(0.1)
                if stop_event and stop_event.is_set():
                    break

            round_results = []
            
            async def process_task(index, task):
                async with semaphore:
                    if stop_event and stop_event.is_set():
                        return
                    
                    target_email = task["email"].strip()
                    gpt_id_raw = task["gpt"].strip()
                    if not target_email or not gpt_id_raw:
                        return
                    
                    gpt_id = gpt_id_raw.split('@')[0]
                    prefix = f"[재시도 {retry_round - 1}회차] " if retry_round > 1 else ""
                    log(f"{prefix}[{index+1}/{len(current_tasks)}] 새 탭 열기: '{target_email}' → '{gpt_id}'")
                    
                    res = await process_single_job_async(index, task, context, stop_event, log)
                    if res:
                        round_results.append(res)
                    
                    # 다음 작업 전 약간의 딜레이
                    for _ in range(10):
                        if stop_event and stop_event.is_set():
                            break
                        await asyncio.sleep(0.1)

            coros = [process_task(i, task) for i, task in enumerate(current_tasks)]
            await asyncio.gather(*coros)

            if stop_event and stop_event.is_set():
                completed_emails = {r["email"] for r in round_results}
                remaining = [t for t in current_tasks if t["email"].strip() not in completed_emails]
                for t in remaining:
                    round_results.append({
                        "email": t["email"].strip(),
                        "gpt": t["gpt"].strip().split('@')[0],
                        "status": "FAIL",
                        "reason": "사용자 중단"
                    })
                accumulated_results.extend(round_results)
                break

            round_successes = [r for r in round_results if r["status"] != "FAIL"]
            round_failures = [r for r in round_results if r["status"] == "FAIL"]

            accumulated_results.extend(round_successes)
            current_fail_count = len(round_failures)

            if current_fail_count == 0:
                break

            if current_fail_count >= prev_fail_count:
                # 실패 개수가 줄어들지 않으면 재시도를 멈추고 실패 건들도 누적 결과에 병합
                accumulated_results.extend(round_failures)
                break

            prev_fail_count = current_fail_count
            current_tasks = [{"email": r["email"], "gpt": r["gpt"]} for r in round_failures]

        log("🎉 모든 자동화 작업이 끝났습니다!")
        await browser.close()

    return accumulated_results
