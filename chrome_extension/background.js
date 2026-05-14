chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "startJobs") {
    processJobs(request.tasks).then((results) => {
      sendResponse({ status: "done", results: results });
    });
    return true; // 비동기 응답 대기
  }
  
  // 범용 CDP 클릭 핸들러 (백그라운드 탭에서 클릭 이벤트를 강제 발생)
  if (request.action === "cdpClick") {
    const tabId = sender.tab.id;
    (async () => {
      try {
        if (request.x !== undefined && request.y !== undefined) {
           await new Promise(r => chrome.debugger.sendCommand({tabId}, "Input.dispatchMouseEvent", {
               type: "mousePressed", x: request.x, y: request.y, button: "left", clickCount: 1
           }, r));
           await new Promise(r => setTimeout(r, 50));
           await new Promise(r => chrome.debugger.sendCommand({tabId}, "Input.dispatchMouseEvent", {
               type: "mouseReleased", x: request.x, y: request.y, button: "left", clickCount: 1
           }, r));
        }
        sendResponse({success: true});
      } catch(e) {
        console.error("Debugger click error:", e);
        sendResponse({success: false});
      }
    })();
    return true;
  }
  
  // 컨텐츠 스크립트에서 진짜 키보드 입력을 요청했을 때 처리 (Playwright 완벽 모방)
  if (request.action === "typeAndTab") {
    const tabId = sender.tab.id;
    (async () => {
      try {
        // 크롬 브라우저 정책상 탭이 포커스를 잃으면 키보드 이벤트가 무시될 수 있으므로
        // 아주 잠깐 해당 탭을 화면 맨 앞으로(활성화) 가져와서 포커스를 강제합니다.
        await chrome.tabs.update(tabId, { active: true });
        await new Promise(r => setTimeout(r, 200)); // 활성화 후 0.2초 대기


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
  const MAX_CONCURRENT = 3;
  let activeCount = 0;
  let currentIndex = 0;
  let completedCount = 0;
  let successCount = 0;
  let failCount = 0;
  
  const startTime = Date.now();
  const jobResults = [];
  
  return new Promise((resolve) => {
    async function runNext() {
      if (currentIndex >= tasks.length && activeCount === 0) {
        chrome.notifications.create({
          type: 'basic',
          iconUrl: 'icon.png',
          title: 'GPT 자동화 완료',
          message: `작업 완료 - 성공: ${successCount}건, 실패: ${failCount}건`
        });
        
        const elapsedTime = Math.round((Date.now() - startTime) / 1000);
        
        // 결과 저장 및 리포트 탭 열기
        chrome.storage.local.set({
          gptAutoResults: {
            tasksTotal: tasks.length,
            successCount,
            failCount,
            elapsedTime,
            jobResults
          }
        }, () => {
          chrome.tabs.create({ url: chrome.runtime.getURL("report.html") });
        });
        
        resolve({ successCount, failCount });
        return;
      }
      
      while (activeCount < MAX_CONCURRENT && currentIndex < tasks.length) {
        const i = currentIndex++;
        const task = tasks[i];
        activeCount++;
        
        processSingleJob(task, i, tasks.length).then((result) => {
          if (result.success) {
            successCount++;
            chrome.runtime.sendMessage({ action: "logResult", text: `✅ 성공: ${task.email}` });
            jobResults.push({ email: task.email, gpt: task.gpt, status: 'OK' });
          } else {
            failCount++;
            chrome.runtime.sendMessage({ action: "logResult", text: `❌ 실패: ${task.email}` });
            jobResults.push({ email: task.email, gpt: task.gpt, status: 'FAIL', reason: result.error });
          }
        }).finally(() => {
          activeCount--;
          completedCount++;
          chrome.runtime.sendMessage({ action: "updateStatus", text: `진행도: ${completedCount}/${tasks.length} 완료 (동시 처리 중...)` });
          runNext();
        });
      }
    }
    
    // 처음 실행
    runNext();
  });
}

async function processSingleJob(task, index, total) {
  const url = `https://groups.google.com/a/ablearn.kr/g/${task.gpt}/members`;
  let result = { success: false, error: "알 수 없는 오류" };

  // 탭 생성 (새 창/팝업으로 열기)
  // 구글 보안 정책 우회를 위해 별도의 팝업창으로 열어 포커스를 유지합니다.
  const win = await chrome.windows.create({ 
    url: url, 
    type: 'popup', 
    width: 800, 
    height: 600, 
    focused: true 
  });
  const tab = win.tabs[0];

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
    // 디버거 연결
    await new Promise(r => chrome.debugger.attach({tabId: tab.id}, "1.3", r));
    
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['content.js']
    });

    // 스크립트에 이메일 전달 후 끝날 때까지 대기
    let res = await new Promise((resolve) => {
      chrome.tabs.sendMessage(tab.id, { action: "runAddMember", email: task.email }, (res) => {
        resolve(res);
      });
    });
    if (res && res.success) {
      result = { success: true };
    } else if (res && res.error) {
      result = { success: false, error: res.error };
    } else {
      result = { success: false, error: "응답 시간 초과 또는 알 수 없는 에러" };
    }
    
    // 디버거 연결 해제
    await new Promise(r => chrome.debugger.detach({tabId: tab.id}, r));
  } catch(e) {
    console.error(e);
    result = { success: false, error: e.toString() };
  }
  
  // 작업 완료 후 탭 닫기
  await chrome.tabs.remove(tab.id);
  
  // 다음 사람 작업 전 약간 대기 (안정성)
  await new Promise(r => setTimeout(r, 1000));
  
  return result;
}
