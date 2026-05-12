chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "startJobs") {
    processJobs(request.tasks).then(() => {
      sendResponse({ status: "done" });
    });
    return true; // 비동기 응답 대기
  }
  
  // 컨텐츠 스크립트에서 진짜 키보드 입력을 요청했을 때 처리 (Playwright 완벽 모방)
  if (request.action === "typeAndTab") {
    const tabId = sender.tab.id;
    (async () => {
      try {
        // 1. 진짜 사람처럼 한 글자씩 타이핑
        for(let i=0; i<request.text.length; i++) {
            await new Promise(r => chrome.debugger.sendCommand({tabId}, "Input.dispatchKeyEvent", {
                type: "char", text: request.text[i]
            }, r));
            await new Promise(r => setTimeout(r, 30));
        }
        await new Promise(r => setTimeout(r, 1000));
        
        // 2. 진짜 키보드 탭(Tab) 키 누르기
        await new Promise(r => chrome.debugger.sendCommand({tabId}, "Input.dispatchKeyEvent", {
            type: "keyDown", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9
        }, r));
        await new Promise(r => chrome.debugger.sendCommand({tabId}, "Input.dispatchKeyEvent", {
            type: "keyUp", key: "Tab", code: "Tab", windowsVirtualKeyCode: 9, nativeVirtualKeyCode: 9
        }, r));
        
        sendResponse({success: true});
      } catch(e) {
        console.error("Debugger error:", e);
        sendResponse({success: false});
      }
    })();
    return true;
  }
});

async function processJobs(tasks) {
  for (let i = 0; i < tasks.length; i++) {
    const task = tasks[i];
    const url = `https://groups.google.com/a/ablearn.kr/g/${task.gpt}/members`;
    
    chrome.runtime.sendMessage({ action: "updateStatus", text: `[${i+1}/${tasks.length}] ${task.email} 님을 ${task.gpt} 에 추가 중...` });

    // 탭 생성
    const tab = await chrome.tabs.create({ url: url, active: true });

    // 탭 로딩 완료 대기
    await new Promise(resolve => {
      chrome.tabs.onUpdated.addListener(function listener(tabId, info) {
        if (tabId === tab.id && info.status === 'complete') {
          chrome.tabs.onUpdated.removeListener(listener);
          setTimeout(resolve, 2000); // 로딩 후 2초 안정화
        }
      });
    });

    // 화면 자동화 스크립트 실행
    try {
      // Playwright 와 똑같은 하드웨어 제어 권한(디버거) 부여
      await new Promise(r => chrome.debugger.attach({tabId: tab.id}, "1.3", r));
      
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
      });

      // 스크립트에 이메일 전달 후 끝날 때까지 대기
      await new Promise((resolve) => {
        chrome.tabs.sendMessage(tab.id, { action: "runAddMember", email: task.email }, (res) => {
          resolve(res);
        });
      });
      
      // 디버거 연결 해제
      await new Promise(r => chrome.debugger.detach({tabId: tab.id}, r));
    } catch(e) {
      console.error(e);
    }
    
    // 작업 완료 후 탭 닫기
    await chrome.tabs.remove(tab.id);
    
    // 다음 사람 작업 전 1초 대기
    await new Promise(r => setTimeout(r, 1000));
  }
}
