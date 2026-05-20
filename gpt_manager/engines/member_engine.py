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

async def run_add_members_async(tasks, log_callback, login_event=None, stop_event=None):
    def log(msg):
        log_callback("멤버추가", msg)

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log("❌ Playwright가 설치되어 있지 않습니다. 'pip3 install playwright && playwright install chromium' 을 실행해주세요.")
        return [{"status": "FAIL", "reason": "Playwright 미설치"}]

    results = []

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
        
        log("✅ 로그인 확인 — 자동 추가를 병렬로 시작합니다.")

        # 최대 동시 실행할 탭 개수 (구글 차단 방지)
        MAX_CONCURRENT_TABS = 3
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TABS)

        async def process_task(index, task):
            async with semaphore:
                if stop_event and stop_event.is_set():
                    return
                
                target_email = task["email"].strip()
                gpt_id_raw = task["gpt"].strip()
                if not target_email or not gpt_id_raw:
                    return

                gpt_id = gpt_id_raw.split('@')[0]
                url = f"https://groups.google.com/a/ablearn.kr/g/{gpt_id}/members"
                
                log(f"[{index+1}/{len(tasks)}] 새 탭 열기: '{target_email}' → '{gpt_id}'")
                
                page = await context.new_page()
                try:
                    await page.goto(url)
                    await page.wait_for_load_state("networkidle")

                    # '회원 추가' 버튼 클릭
                    add_btn = page.locator("text=회원 추가").first
                    if await add_btn.count() == 0:
                        add_btn = page.get_by_label("회원 추가")
                    await add_btn.wait_for(state="visible", timeout=10000)
                    await add_btn.click()
                    await asyncio.sleep(1.5)

                    # 이메일 입력
                    member_input = page.get_by_label("그룹 멤버")
                    await member_input.wait_for(state="visible", timeout=5000)
                    await member_input.click()
                    await member_input.fill(target_email)
                    await asyncio.sleep(1)
                    await member_input.click()
                    await member_input.press("Tab")
                    await asyncio.sleep(1)

                    # 하단 '회원 추가' 제출 버튼 클릭
                    confirm_add_btn = page.get_by_role("button", name="회원 추가").last
                    await confirm_add_btn.wait_for(state="visible", timeout=5000)
                    await confirm_add_btn.click()

                    # "회원이 업데이트되었습니다" 모달 대기 (유일한 성공 조건)
                    try:
                        success_title = page.locator("text=회원이 업데이트되었습니다")
                        await success_title.wait_for(state="visible", timeout=6000)

                        ok_btn = page.get_by_role("button", name="확인")
                        if await ok_btn.is_visible():
                            await ok_btn.click()
                            await asyncio.sleep(0.5)

                        log(f"✅ 추가 완료: {target_email} → {gpt_id}")
                        results.append({"email": target_email, "gpt": gpt_id, "status": "OK"})
                    except Exception:
                        err_text = "성공 팝업(회원이 업데이트되었습니다)을 찾지 못했습니다."
                        try:
                            # 팝업이 안 뜬 경우, 다른 스낵바나 에러 메시지 추출
                            alert_box = page.locator("[role='alert'], .m2-snackbar")
                            if await alert_box.count() > 0 and await alert_box.first.is_visible():
                                err_text = await alert_box.first.inner_text()
                        except:
                            pass
                        
                        log(f"❌ 추가 실패 ({target_email}): {err_text}")
                        results.append({"email": target_email, "gpt": gpt_id, "status": "FAIL", "reason": err_text})
                finally:
                    await page.close()
                    await asyncio.sleep(0.5)

        coros = [process_task(i, task) for i, task in enumerate(tasks)]
        await asyncio.gather(*coros)

        log("🎉 모든 자동화 작업이 끝났습니다!")
        await browser.close()

    return results
