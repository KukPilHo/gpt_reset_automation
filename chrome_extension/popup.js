const gridBody = document.getElementById('gridBody');
const startBtn = document.getElementById('startBtn');
const clearBtn = document.getElementById('clearBtn');
const stopBtn = document.getElementById('stopBtn');
const statusDiv = document.getElementById('status');
const logArea = document.getElementById('logArea');

// ===== 행(Row) 생성 =====
function createRow(email = '', gpt = '', isExample = false) {
  const tr = document.createElement('tr');
  if (isExample) tr.classList.add('example-row');
  
  const rowNum = gridBody.children.length + 1;
  tr.innerHTML = `
    <td class="row-num">${rowNum}</td>
    <td><input type="text" value="${email}" placeholder="${isExample ? '' : '이메일 입력'}"></td>
    <td><input type="text" value="${gpt}" placeholder="${isExample ? '' : 'gpt번호'}"></td>
  `;

  // 각 input에 이벤트 연결
  tr.querySelectorAll('input').forEach(input => {
    input.addEventListener('input', onCellInput);
    input.addEventListener('focus', onCellFocus);
  });

  return tr;
}

// ===== 행 번호 재정렬 =====
function renumberRows() {
  Array.from(gridBody.children).forEach((tr, i) => {
    const numCell = tr.querySelector('.row-num');
    if (numCell) numCell.textContent = i + 1;
  });
}

// ===== 빈 행이 하단에 최소 1개 이상 있는지 확인 후 자동 추가 =====
function ensureEmptyRows() {
  const rows = Array.from(gridBody.children);
  // 마지막 행이 비어있는지 확인
  let emptyTailCount = 0;
  for (let i = rows.length - 1; i >= 0; i--) {
    const inputs = rows[i].querySelectorAll('input');
    const email = inputs[0].value.trim();
    const gpt = inputs[1].value.trim();
    if (!email && !gpt) {
      emptyTailCount++;
    } else {
      break;
    }
  }
  // 빈 행이 1개 미만이면 추가
  if (emptyTailCount < 1) {
    gridBody.appendChild(createRow());
    renumberRows();
  }
}

// ===== 셀 입력 시 =====
function onCellInput(e) {
  // example-row 클래스 제거 (사용자가 수정하면 예시가 아님)
  const tr = e.target.closest('tr');
  if (tr) tr.classList.remove('example-row');
  
  ensureEmptyRows();
}

// ===== 셀 포커스 시 (예시 행 클릭하면 텍스트 전체 선택) =====
function onCellFocus(e) {
  const tr = e.target.closest('tr');
  if (tr && tr.classList.contains('example-row')) {
    e.target.select();
  }
}

// ===== 붙여넣기 처리 (셀에서 Ctrl+V) =====
gridBody.addEventListener('paste', (e) => {
  const pasteData = (e.clipboardData || window.clipboardData).getData('text');
  if (!pasteData) return;
  
  // 멀티라인 데이터인 경우에만 가로채기
  if (!pasteData.includes('\n') && !pasteData.includes('\t')) return;
  
  e.preventDefault();

  const lines = pasteData.split('\n').map(l => l.trim()).filter(l => l !== '');
  const rowsData = lines.map(line => {
    // 탭 구분 우선
    if (line.includes('\t')) {
      return line.split(/\t+/).map(p => p.trim());
    }
    // 탭이 없으면 공백 구분 (이메일에는 공백이 없으므로 안전)
    return line.split(/\s+/).map(p => p.trim());
  });

  // 현재 포커스된 행 위치 파악
  let targetInput = e.target;
  let startRowIndex = 0;
  if (targetInput && targetInput.tagName === 'INPUT') {
    const tr = targetInput.closest('tr');
    startRowIndex = Array.from(gridBody.children).indexOf(tr);
    if (startRowIndex < 0) startRowIndex = 0;
  }

  // 필요한 만큼 행 확장
  while (gridBody.children.length < startRowIndex + rowsData.length) {
    gridBody.appendChild(createRow());
  }

  // 데이터 채우기
  rowsData.forEach((cols, i) => {
    const tr = gridBody.children[startRowIndex + i];
    tr.classList.remove('example-row');
    const inputs = tr.querySelectorAll('input');
    if (cols[0]) inputs[0].value = cols[0];
    if (cols[1]) inputs[1].value = cols[1];
  });

  renumberRows();
  ensureEmptyRows();
});

// ===== 초기화 =====
function initGrid() {
  gridBody.innerHTML = '';
  // 예시 데이터 1행
  gridBody.appendChild(createRow('peter@gmail.com', 'gpt10@ablearn.kr', true));
  // 빈 행 3개
  for (let i = 0; i < 3; i++) {
    gridBody.appendChild(createRow());
  }
  renumberRows();
}

// ===== 초기화 버튼 =====
clearBtn.addEventListener('click', () => {
  initGrid();
  statusDiv.innerText = '';
  logArea.innerHTML = '';
  startBtn.disabled = false;
});

// ===== 시작 버튼 =====
startBtn.addEventListener('click', () => {
  const tasks = [];
  const rows = gridBody.querySelectorAll('tr');
  
  rows.forEach(row => {
    // 예시 행(수정 안 한)은 건너뛰기
    if (row.classList.contains('example-row')) return;
    
    const inputs = row.querySelectorAll('input');
    if (inputs.length < 2) return;
    
    const email = inputs[0].value.trim();
    let gpt = inputs[1].value.trim();
    
    // 빈 행 무시 (공란 오류 방지)
    if (!email || !gpt) return;
    
    // gpt10@ablearn.kr → gpt10 자동 추출
    gpt = gpt.split('@')[0];
    tasks.push({ email, gpt });
  });

  if (tasks.length === 0) {
    alert("입력된 데이터가 없습니다.\n이메일과 GPT 계정을 모두 입력해주세요.");
    return;
  }

  statusDiv.innerText = `총 ${tasks.length}명 작업 시작...`;
  logArea.innerHTML = '';
  
  // 버튼 상태 토글
  startBtn.style.display = 'none';
  stopBtn.style.display = 'inline-block';
  stopBtn.disabled = false;
  stopBtn.innerText = '■ 작업 중단';
  clearBtn.disabled = true;

  chrome.runtime.sendMessage({ action: "startJobs", tasks: tasks }, (response) => {
    // 버튼 상태 원상복구
    startBtn.style.display = 'inline-block';
    startBtn.disabled = false;
    stopBtn.style.display = 'none';
    clearBtn.disabled = false;

    if (response && response.status === "done") {
      let msg = "";
      if (response.results.isCancelled) {
        msg = `🛑 작업을 중단했습니다.\n\n성공: ${response.results.successCount}건\n실패: ${response.results.failCount}건`;
      } else {
        msg = `🎉 작업이 모두 완료되었습니다!\n\n성공: ${response.results.successCount}건\n실패: ${response.results.failCount}건`;
      }
      statusDiv.innerText = msg;
      alert(msg);
    }
  });
});

// ===== 중단 버튼 =====
stopBtn.addEventListener('click', () => {
  stopBtn.disabled = true;
  stopBtn.innerText = '중단 중...';
  chrome.runtime.sendMessage({ action: "stopJobs" }, (response) => {
    if (response && response.status === "stopped") {
      statusDiv.innerText = "사용자 요청에 의해 작업을 중단하는 중입니다...";
      // 즉시 버튼 복구
      startBtn.style.display = 'inline-block';
      startBtn.disabled = false;
      stopBtn.style.display = 'none';
      stopBtn.innerText = '■ 작업 중단';
      clearBtn.disabled = false;
    }
  });
});

// ===== 진행 상태 수신 =====
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "updateStatus") {
    statusDiv.innerText = msg.text;
  } else if (msg.action === "logResult") {
    const div = document.createElement('div');
    div.innerText = msg.text;
    if (msg.text.includes('❌')) {
      div.style.color = '#d32f2f'; // 에러 시 붉은색
    } else {
      div.style.color = '#388e3c'; // 성공 시 초록색
    }
    logArea.appendChild(div);
    logArea.scrollTop = logArea.scrollHeight;
  }
});

// ===== 페이지 로드 시 상태 확인 및 초기화 =====
chrome.runtime.sendMessage({ action: "getRunningState" }, (response) => {
  if (response && response.isRunning) {
    // 실행 중인 UI 상태로 설정
    startBtn.style.display = 'none';
    stopBtn.style.display = 'inline-block';
    stopBtn.disabled = false;
    stopBtn.innerText = '■ 작업 중단';
    clearBtn.disabled = true;

    // 작업 리스트 복구
    if (response.tasks && response.tasks.length > 0) {
      gridBody.innerHTML = '';
      response.tasks.forEach(task => {
        gridBody.appendChild(createRow(task.email, task.gpt));
      });
      renumberRows();
    }

    // 진행 상태 및 로그 복구
    statusDiv.innerText = response.statusText;
    logArea.innerHTML = '';
    response.logs.forEach(log => {
      const div = document.createElement('div');
      div.innerText = log.text;
      if (log.text.includes('❌')) {
        div.style.color = '#d32f2f';
      } else {
        div.style.color = '#388e3c';
      }
      logArea.appendChild(div);
    });
    logArea.scrollTop = logArea.scrollHeight;
  } else {
    initGrid();
  }
});
