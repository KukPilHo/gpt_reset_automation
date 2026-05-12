import pandas as pd
from playwright.sync_api import sync_playwright
import time
import sys

# ================= 설정 부분 =================
# 엑셀 파일 이름 (스크립트와 같은 폴더에 있어야 합니다)
EXCEL_FILE = "list.xlsx"  
# ===========================================

def main():
    try:
        # 엑셀 파일 읽기 (A열: 교육생, B열: GPT계정)
        df = pd.read_excel(EXCEL_FILE)
    except FileNotFoundError:
        print(f"❌ '{EXCEL_FILE}' 파일을 찾을 수 없습니다. 파이썬 스크립트와 같은 폴더에 엑셀 파일을 넣어주세요.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 엑셀 파일 읽기 오류: {e}")
        sys.exit(1)

    with sync_playwright() as p:
        # 브라우저 실행 (headless=False 로 설정하여 봇이 아닌 일반 브라우저처럼 띄움)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # 구글 로그인 페이지 열기
        page.goto("https://accounts.google.com/")
        print("=========================================================")
        print("🟢 브라우저가 열렸습니다. 구글 계정으로 직접 1회 로그인해주세요.")
        print("🟢 로그인이 완전히 끝난 후(내 계정 홈 화면이 보이면) 터미널 창에서 [Enter] 키를 누르세요.")
        print("=========================================================")
        input("로그인 완료 후 터미널 창에서 엔터 키를 누르세요...")

        # 엑셀 데이터 한 줄씩 순회하며 실행
        # pandas는 기본적으로 엑셀의 1행을 제목(헤더)으로 인식하므로, 실제 데이터는 2행부터 읽기 시작합니다.
        for index, row in df.iterrows():
            target_email = str(row.iloc[0]).strip() # A열(1열): 추가할 이메일 주소
            gpt_id_raw = str(row.iloc[1]).strip()   # B열(2열): 주소창에 들어갈 그룹 ID (예: gpt10)
            
            if pd.isna(gpt_id_raw) or not gpt_id_raw or gpt_id_raw == 'nan':
                continue
            
            # 혹시 이메일 형식(gpt10@ablearn.kr)으로 들어왔을 경우를 대비해 앞부분만 추출
            gpt_id = gpt_id_raw.split('@')[0]
            
            # 해당 그룹 주소로 이동
            url = f"https://groups.google.com/a/ablearn.kr/g/{gpt_id}/members"
            print(f"\n[엑셀 {index+2}행] '{target_email}' 이메일을 '{gpt_id}' 그룹에 추가하는 중...")
            
            try:
                # 1. 주소창 입력 및 이동
                page.goto(url)
                page.wait_for_load_state("networkidle")
                
                # 2. 첫 화면 상단의 '회원 추가' 버튼 클릭 (Codegen 반영)
                add_btn = page.get_by_label("회원 추가")
                add_btn.wait_for(state="visible", timeout=10000)
                add_btn.click()
                time.sleep(1.5) # 모달창 애니메이션 대기
                
                # 3. '그룹 멤버' 란에 이메일 입력 (Codegen 반영)
                member_input = page.get_by_label("그룹 멤버")
                member_input.wait_for(state="visible", timeout=5000)
                member_input.click() # 입력창 클릭
                member_input.fill(target_email) # 이메일 입력
                time.sleep(1)
                member_input.click() # 다시 한번 클릭 (포커스 유지)
                member_input.press("Tab") # 탭 키 입력 (버튼 활성화)
                time.sleep(1)
                
                # 4. 하단 '회원 추가' 버튼 클릭 (Codegen 반영)
                confirm_add_btn = page.get_by_role("button", name="회원 추가")
                confirm_add_btn.wait_for(state="visible", timeout=5000)
                confirm_add_btn.click()
                
                # 5. 확인 팝업 대기 (Codegen 반영)
                time.sleep(2)
                try:
                    ok_btn = page.get_by_role("button", name="확인")
                    if ok_btn.is_visible(timeout=3000):
                        ok_btn.click()
                        time.sleep(1)
                except:
                    pass # 확인 창이 없으면 정상적으로 추가된 것으로 간주
                
                print(f"✅ 추가 완료: {target_email} -> {gpt_id}")
                time.sleep(1) # 다음 루프 전 안정성을 위해 약간 대기

            except Exception as e:
                print(f"❌ 추가 실패 ({target_email}): 프로세스 도중 에러가 발생했습니다.")
                print("구글 그룹스 화면을 확인하시고, 수동으로 처리하시거나 봇 차단(로봇이 아닙니다)이 떴는지 확인해주세요.")
                print("문제를 해결한 후 다음 순서로 넘어가려면 터미널 창에서 [Enter] 키를 누르세요...")
                input() # 에러 시 멈춰서 사용자가 직접 제어할 수 있도록 함

        print("\n🎉 모든 자동화 작업이 끝났습니다!")
        browser.close()

if __name__ == "__main__":
    main()
