chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "runAddMember") {
    runAddMember(request.email)
      .then((result) => sendResponse(result))
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

/**
 * 현재 멤버 목록 페이지에서 해당 이메일이 이미 존재하는지 확인합니다.
 * 두 가지 방법을 사용하여 신뢰성을 확보:
 * 1. AF_initDataCallback의 ds:12 데이터에서 이메일 파싱
 * 2. 페이지 전체 텍스트에서 이메일 검색 (폴백)
 */
function checkEmailExists(email) {
  const emailLower = email.toLowerCase().trim();
  
  // 방법 1: ds:12 스크립트 데이터에서 멤버 이메일 목록 추출
  try {
    const scripts = document.querySelectorAll('script.ds\\:12, script[class="ds:12"]');
    for (const script of scripts) {
      const text = script.textContent || '';
      // 이메일 패턴 매칭 (JSON 내에서 "email@domain.com" 형태로 존재)
      const emailRegex = /[\w._%+-]+@[\w.-]+\.[a-zA-Z]{2,}/g;
      const matches = text.match(emailRegex);
      if (matches) {
        for (const match of matches) {
          if (match.toLowerCase() === emailLower) {
            return true;
          }
        }
      }
    }
  } catch(e) {
    console.warn('ds:12 파싱 실패, 폴백으로 진행:', e);
  }
  
  // 방법 2: 페이지 전체 HTML에서 이메일 검색
  // (렌더링된 텍스트와 스크립트 데이터 모두 포함)
  try {
    const bodyHTML = document.body.innerHTML;
    // 정확한 이메일 매칭을 위해 이메일 앞뒤에 구분자가 있는지 확인
    // JSON 데이터에서는 "email@domain" 형태로 있음
    if (bodyHTML.toLowerCase().includes('"' + emailLower + '"') ||
        bodyHTML.toLowerCase().includes('>' + emailLower + '<') ||
        bodyHTML.toLowerCase().includes(',' + emailLower + ',')) {
      return true;
    }
  } catch(e) {
    console.warn('HTML 텍스트 검색 실패:', e);
  }

  // 방법 3: 렌더링된 innerText에서 이메일 검색 (최종 폴백)
  try {
    const bodyText = document.body.innerText;
    if (bodyText.toLowerCase().includes(emailLower)) {
      return true;
    }
  } catch(e) {
    console.warn('innerText 검색 실패:', e);
  }
  
  return false;
}

async function runAddMember(email) {
  try {
    // ★ 사전 체크: 추가하려는 이메일이 이미 멤버 목록에 있는지 확인
    if (checkEmailExists(email)) {
      console.log(`[중복 감지] ${email}은(는) 이미 그룹에 존재합니다.`);
      return { success: true, alreadyExists: true };
    }

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
        return { success: true, alreadyExists: false };
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

        // ★ 에러 발생 후 사후 체크: 에러가 났지만 실제로는 추가가 완료된 경우
        // 페이지를 새로고침하여 최신 멤버 목록을 확인할 수도 있지만,
        // 현재 페이지의 데이터에서도 확인 가능 (구글이 DOM을 업데이트할 수 있음)
        // 일단 현재 DOM 상태에서 체크
        if (checkEmailExists(email)) {
          console.log(`[사후 확인] ${email}이(가) 에러 후에도 멤버 목록에 존재합니다 → 성공 처리`);
          return { success: true, alreadyExists: true };
        }

        throw new Error(errText);
    }
    
  } catch(e) {
    console.error(e);
    throw e;
  }
}
