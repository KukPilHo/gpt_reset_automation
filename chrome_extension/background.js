let isRunning = false;
let isCancelled = false;
let currentProgressText = "";
let currentLogs = [];
let runningTasks = [];
let activeWindowIds = new Set();

function safeSendMessage(message) {
  if (message.action === "updateStatus") {
    currentProgressText = message.text;
  } else if (message.action === "logResult") {
    currentLogs.push({ text: message.text });
  }
  chrome.runtime.sendMessage(message, () => {
    const err = chrome.runtime.lastError; // Ignore error when popup is closed
  });
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "startJobs") {
    isRunning = true;
    isCancelled = false;
    currentProgressText = `총 ${request.tasks.length}명 작업 시작...`;
    currentLogs = [];
    runningTasks = request.tasks;

    const originalTotal = request.originalTotal || request.tasks.length;
    const previousResults = request.previousResults || [];
    processJobsWithAutoRetry(request.tasks, originalTotal, previousResults).then((results) => {
      isRunning = false;
      sendResponse({ status: "done", results: results });
    });
    return true; // 비동기 응답 대기
  }

  if (request.action === "stopJobs") {
    isCancelled = true;
    isRunning = false;

    // 즉시 실행 중인 모든 팝업 창 닫기
    (async () => {
      for (const winId of activeWindowIds) {
        try {
          await chrome.windows.remove(winId);
        } catch (e) {
          console.error("Error closing window on cancel:", e);
        }
      }
      activeWindowIds.clear();
    })();

    sendResponse({ status: "stopped" });
    return true;
  }

  if (request.action === "getRunningState") {
    sendResponse({
      isRunning: isRunning,
      statusText: currentProgressText,
      logs: currentLogs,
      tasks: runningTasks
    });
    return true;
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

async function processJobsWithAutoRetry(tasks, originalTotal, previousResults) {
  const overallStartTime = Date.now();
  let accumulatedResults = [...previousResults];
  let currentTasks = tasks;
  let prevFailCount = Infinity;
  let retryRound = 0;

  while (true) {
    if (isCancelled) break;
    retryRound++;

    if (retryRound > 1) {
      safeSendMessage({
        action: "logResult",
        text: `🔄 자동 재시도 ${retryRound - 1}회차 시작 (실패 ${currentTasks.length}건)`
      });
      // 재시도 전 잠시 대기 (중단 감지를 위해 100ms씩 슬립)
      for (let i = 0; i < 20; i++) {
        if (isCancelled) break;
        await new Promise(r => setTimeout(r, 100));
      }
      if (isCancelled) break;
    }

    const previousSuccessCount = accumulatedResults.length;
    const roundResults = await processJobsRound(currentTasks, retryRound, previousSuccessCount, originalTotal);

    if (isCancelled) {
      // 중단된 경우 미처리 항목 수집
      const completedEmails = new Set(roundResults.map(r => r.email));
      const remainingTasks = currentTasks.filter(t => !completedEmails.has(t.email));
      const cancelResults = remainingTasks.map(t => ({
        email: t.email,
        gpt: t.gpt,
        status: 'FAIL',
        reason: '사용자 중단'
      }));
      accumulatedResults = accumulatedResults.concat(roundResults).concat(cancelResults);
      break;
    }

    const roundSuccesses = roundResults.filter(j => j.status !== 'FAIL');
    const roundFailures = roundResults.filter(j => j.status === 'FAIL');

    accumulatedResults = accumulatedResults.concat(roundSuccesses);

    const currentFailCount = roundFailures.length;

    if (currentFailCount === 0) {
      // 모든 항목 성공
      break;
    }

    if (currentFailCount >= prevFailCount) {
      // 실패 개수가 줄지 않음 - 재시도 중단
      accumulatedResults = accumulatedResults.concat(roundFailures);
      break;
    }

    // 실패 개수 감소 - 다시 시도
    prevFailCount = currentFailCount;
    currentTasks = roundFailures.map(j => ({ email: j.email, gpt: j.gpt }));
  }

  const totalElapsed = Math.round((Date.now() - overallStartTime) / 1000);
  const finalSuccessCount = accumulatedResults.filter(j => j.status !== 'FAIL').length;
  const finalFailCount = accumulatedResults.filter(j => j.status === 'FAIL').length;

  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icon.png',
    title: isCancelled ? 'GPT 자동화 중단됨' : 'GPT 자동화 완료',
    message: isCancelled 
      ? `사용자에 의해 중단되었습니다. (성공: ${finalSuccessCount}건)` 
      : `작업 완료 - 성공: ${finalSuccessCount}건, 실패: ${finalFailCount}건`
  });

  chrome.storage.local.set({
    gptAutoResults: {
      tasksTotal: originalTotal,
      originalTotal: originalTotal,
      successCount: finalSuccessCount,
      failCount: finalFailCount,
      elapsedTime: totalElapsed,
      jobResults: accumulatedResults
    }
  }, () => {
    chrome.tabs.create({ url: chrome.runtime.getURL("report.html") });
  });

  return { successCount: finalSuccessCount, failCount: finalFailCount, isCancelled: isCancelled };
}

async function processJobsRound(tasks, retryRound, previousSuccessCount, originalTotal) {
  const MAX_CONCURRENT = 6;
  let activeCount = 0;
  let currentIndex = 0;
  let completedCount = 0;
  const jobResults = [];

  const prefix = retryRound > 1 ? `[재시도 ${retryRound - 1}회차] ` : '';

  return new Promise((resolve) => {
    async function runNext() {
      if (isCancelled) {
        resolve(jobResults);
        return;
      }

      if (currentIndex >= tasks.length && activeCount === 0) {
        resolve(jobResults);
        return;
      }

      while (activeCount < MAX_CONCURRENT && currentIndex < tasks.length && !isCancelled) {
        const i = currentIndex++;
        const task = tasks[i];
        activeCount++;

        processSingleJob(task, i, tasks.length).then((result) => {
          if (isCancelled) {
            jobResults.push({ email: task.email, gpt: task.gpt, status: 'FAIL', reason: '사용자 중단' });
            return;
          }
          if (result.success && result.alreadyExists) {
            safeSendMessage({ action: "logResult", text: `${prefix}🔵 이미 추가됨: ${task.email}` });
            jobResults.push({ email: task.email, gpt: task.gpt, status: 'ALREADY_EXISTS' });
          } else if (result.success) {
            safeSendMessage({ action: "logResult", text: `${prefix}✅ 성공: ${task.email}` });
            jobResults.push({ email: task.email, gpt: task.gpt, status: 'OK' });
          } else {
            safeSendMessage({ action: "logResult", text: `${prefix}❌ 실패: ${task.email}` });
            jobResults.push({ email: task.email, gpt: task.gpt, status: 'FAIL', reason: result.error });
          }
        }).catch((err) => {
          jobResults.push({ email: task.email, gpt: task.gpt, status: 'FAIL', reason: err.toString() });
        }).finally(() => {
          activeCount--;
          completedCount++;
          const overallCompleted = previousSuccessCount + completedCount;
          if (!isCancelled) {
            safeSendMessage({ action: "updateStatus", text: `${prefix}진행도: ${overallCompleted}/${originalTotal} 완료 (동시 처리 중...)` });
            runNext();
          } else {
            runNext();
          }
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
  let win = null;

  try {
    // 탭 생성 (새 창/팝업으로 열기)
    win = await chrome.windows.create({ 
      url: url, 
      type: 'popup', 
      width: 800, 
      height: 600, 
      focused: true 
    });
    const tab = win.tabs[0];
    activeWindowIds.add(win.id);

    // 탭 로딩 완료 대기
    await new Promise(resolve => {
      chrome.tabs.onUpdated.addListener(function listener(tabId, info) {
        if (tabId === tab.id && info.status === 'complete') {
          chrome.tabs.onUpdated.removeListener(listener);
          setTimeout(resolve, 2000); // 로딩 후 2초 안정화
        }
      });
    });

    if (isCancelled) throw new Error("사용자 중단");

    // 화면 자동화 스크립트 실행
    // 디버거 연결
    await new Promise(r => chrome.debugger.attach({tabId: tab.id}, "1.3", r));
    
    await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ['content.js']
    });

    if (isCancelled) throw new Error("사용자 중단");

    // 스크립트에 이메일 전달 후 끝날 때까지 대기
    let res = await new Promise((resolve) => {
      chrome.tabs.sendMessage(tab.id, { action: "runAddMember", email: task.email }, (res) => {
        resolve(res);
      });
    });
    if (res && res.success) {
      result = { success: true, alreadyExists: !!res.alreadyExists };
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
  } finally {
    if (win && win.id) {
      activeWindowIds.delete(win.id);
      try {
        await chrome.windows.remove(win.id);
      } catch(e) {
        // 이미 닫혔거나 에러난 경우 무시
      }
    }
  }
  
  // 다음 사람 작업 전 약간 대기 (안정성)
  for (let i = 0; i < 10; i++) {
    if (isCancelled) break;
    await new Promise(r => setTimeout(r, 100));
  }
  
  return result;
}
