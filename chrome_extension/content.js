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

async function runAddMember(email) {
  try {
    // 1. 상단 회원 추가 버튼 클릭 (Codegen: get_by_label("회원 추가"))
    let addBtn = await waitForElement('[aria-label="회원 추가"]');
    addBtn.click();
    await wait(1500);
    
    // 2. 그룹 멤버 이메일 입력 (Codegen: get_by_label("그룹 멤버"))
    let input = await waitForElement('input[aria-label="그룹 멤버"]');
    input.focus();
    input.click();
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
    
    // 4. 확인 팝업 (Codegen: get_by_role("button", name="확인"))
    try {
        let okBtn = await waitForButton("확인", 3000);
        okBtn.click();
        await wait(1000);
    } catch(e) {
        // 확인 버튼이 안 뜨는 경우 무시
    }
    
  } catch(e) {
    console.error(e);
    throw e;
  }
}
