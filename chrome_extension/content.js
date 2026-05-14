chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "runAddMember") {
    runAddMember(request.email)
      .then(() => sendResponse({success: true}))
      .catch((e) => sendResponse({success: false, error: e.toString()}));
    return true; // 비동기 응답 처리
  }
});

function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

async function waitForElement(selector, timeout = 10000) {
  let elapsed = 0;
  while(elapsed < timeout) {
    let el = document.querySelector(selector);
    if (el) return el;
    await wait(500);
    elapsed += 500;
  }
  throw new Error(`Timeout waiting for ${selector}`);
}

async function waitForButton(name, timeout = 10000) {
  let elapsed = 0;
  while(elapsed < timeout) {
    let buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
    let matched = buttons.filter(b => {
      let txt = (b.textContent || '').trim();
      let aria = (b.getAttribute('aria-label') || '').trim();
      return txt === name || aria === name;
    });
    
    if (matched.length > 0) {
      // Playwright 처럼 실제로 눈에 보이는(Visible) 버튼만 필터링합니다.
      let visible = matched.filter(b => {
         let rect = b.getBoundingClientRect();
         return rect.width > 0 && rect.height > 0;
      });
      if (visible.length > 0) return visible.pop(); // 모달창은 DOM 끝에 있으므로 pop()
      return matched.pop();
    }
    await wait(500);
    elapsed += 500;
  }
  throw new Error(`Timeout waiting for button: ${name}`);
}

async function clickViaDebugger(el) {
  let rect = el.getBoundingClientRect();
  let x = rect.x + (rect.width / 2);
  let y = rect.y + (rect.height / 2);

  await new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({
      action: "cdpClick",
      x: x,
      y: y
    }, (res) => {
      if(res && res.success) resolve();
      else reject(new Error("CDP click failed"));
    });
  });
}

async function runAddMember(email) {
  try {
    // 1. 상단 회원 추가 버튼 클릭 (Codegen: get_by_label("회원 추가"))
    let addBtn = await waitForElement('[aria-label="회원 추가"]');
    addBtn.click();
    await wait(1500);
    
    // 2. 그룹 멤버 이메일 입력 (Codegen: get_by_label("그룹 멤버"))
    let input = await waitForElement('input[aria-label="그룹 멤버"]');
    // 창이 백그라운드일 때 focus()가 무시되는 것을 막기 위해 CDP로 강제 마우스 클릭
    await clickViaDebugger(input);
    await wait(500);
    
    // 백그라운드(Debugger)를 통해 진짜 키보드로 타이핑 -> 클릭 -> 탭키 누르기 (Codegen 순서 완벽 동일)
    await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({
        action: "typeAndTab",
        text: email
      }, (res) => {
        if(res && res.success) resolve();
        else reject(new Error("Debugger type failed"));
      });
    });
    
    await wait(1500);
    
    // 3. 하단 회원 추가 버튼 클릭 (Codegen: get_by_role("button", name="회원 추가"))
    let confirmBtn = await waitForButton("회원 추가");
    confirmBtn.click();
    await wait(2000);
    
    // 4. "회원이 업데이트되었습니다" 모달 대기 (유일한 성공 조건)
    try {
        let elapsed = 0;
        let successFound = false;
        while(elapsed < 6000) { // 최대 6초 대기
            let walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
            let n;
            while(n = walk.nextNode()) {
                if (n.textContent.includes('회원이 업데이트되었습니다')) {
                    let parent = n.parentElement;
                    if (parent && parent.getBoundingClientRect().height > 0) {
                        successFound = true;
                        break;
                    }
                }
            }
            if (successFound) break;
            await wait(500);
            elapsed += 500;
        }

        if (!successFound) {
            throw new Error("성공 팝업(회원이 업데이트되었습니다)을 찾지 못했습니다.");
        }

        let okBtn = await waitForButton("확인", 3000);
        okBtn.click();
        await wait(500);
    } catch(e) {
        let errText = e.message;
        
        // 에러 팝업이나 다이얼로그가 떠있다면 그 텍스트를 모두 긁어오기
        let dialogs = Array.from(document.querySelectorAll('[role="dialog"], [role="alert"], .m2-snackbar'));
        for (let d of dialogs) {
            // 회원 추가 모달창 본문 자체는 제외 (너무 길어짐)
            if (d.querySelector('input[aria-label="그룹 멤버"]')) continue; 
            
            if (d.innerText && d.innerText.trim().length > 0) {
                // "취소", "확인" 등 버튼 텍스트 제거
                let text = d.innerText.replace(/취소|확인/g, '').trim();
                if (text) {
                    errText = text;
                    break;
                }
            }
        }
        
        // 만약 여전히 타임아웃 에러이고, 회원 추가 버튼이 안 눌렸다면?
        if (errText.includes("Timeout waiting for input") && document.querySelector('input[aria-label="그룹 멤버"]')) {
           errText = "키보드 타이핑이 입력되지 않아 버튼이 비활성화되었습니다.";
        }

        throw new Error(errText);
    }
    
  } catch(e) {
    console.error(e);
    throw e;
  }
}
