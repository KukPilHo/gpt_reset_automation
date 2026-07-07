const startBtn = document.getElementById('startBtn');
const clearBtn = document.getElementById('clearBtn');
const stopBtn = document.getElementById('stopBtn');
const statusDiv = document.getElementById('status');
const logArea = document.getElementById('logArea');

const modeMemberBtn = document.getElementById('modeMemberBtn');
const modeAdminBtn = document.getElementById('modeAdminBtn');
const memberSection = document.getElementById('memberSection');
const adminSection = document.getElementById('adminSection');

let currentMode = 'member'; // 'member' | 'admin'

// ============================================================
// 제네릭 엑셀형 그리드 (열 개수에 상관없이 동작)
// ============================================================
function createGrid(bodyEl, cols, exampleValues) {
  // cols: [{ placeholder }]  형태의 배열

  function createRow(values = [], isExample = false) {
    const tr = document.createElement('tr');
    if (isExample) tr.classList.add('example-row');

    let html = `<td class="row-num"></td>`;
    cols.forEach((c, i) => {
      const val = values[i] != null ? values[i] : '';
      const ph = isExample ? '' : (c.placeholder || '');
      html += `<td><input type="text" value="${val}" placeholder="${ph}"></td>`;
    });
    tr.innerHTML = html;

    tr.querySelectorAll('input').forEach(input => {
      input.addEventListener('input', onCellInput);
      input.addEventListener('focus', onCellFocus);
    });
    return tr;
  }

  function renumber() {
    Array.from(bodyEl.children).forEach((tr, i) => {
      const numCell = tr.querySelector('.row-num');
      if (numCell) numCell.textContent = i + 1;
    });
  }

  function isRowEmpty(tr) {
    return Array.from(tr.querySelectorAll('input')).every(inp => !inp.value.trim());
  }

  function ensureEmptyRows() {
    const rows = Array.from(bodyEl.children);
    let emptyTail = 0;
    for (let i = rows.length - 1; i >= 0; i--) {
      if (isRowEmpty(rows[i])) emptyTail++;
      else break;
    }
    if (emptyTail < 1) {
      bodyEl.appendChild(createRow());
      renumber();
    }
  }

  function onCellInput(e) {
    const tr = e.target.closest('tr');
    if (tr) tr.classList.remove('example-row');
    ensureEmptyRows();
  }

  function onCellFocus(e) {
    const tr = e.target.closest('tr');
    if (tr && tr.classList.contains('example-row')) e.target.select();
  }

  bodyEl.addEventListener('paste', (e) => {
    const pasteData = (e.clipboardData || window.clipboardData).getData('text');
    if (!pasteData) return;
    // 멀티라인/멀티열 데이터인 경우에만 가로채기
    if (!pasteData.includes('\n') && !pasteData.includes('\t')) return;

    e.preventDefault();

    const lines = pasteData.split('\n').map(l => l.trim()).filter(l => l !== '');
    const hasTabs = lines.some(line => line.includes('\t'));

    let targetInput = e.target;
    let startRowIndex = 0;
    let focusedColIndex = 0;
    if (targetInput && targetInput.tagName === 'INPUT') {
      const tr = targetInput.closest('tr');
      startRowIndex = Array.from(bodyEl.children).indexOf(tr);
      if (startRowIndex < 0) startRowIndex = 0;
      const inputsInRow = Array.from(tr.querySelectorAll('input'));
      const colIdx = inputsInRow.indexOf(targetInput);
      if (colIdx >= 0) focusedColIndex = colIdx;
    }

    if (hasTabs) {
      // 여러 열(탭 구분) 데이터
      const rowsData = lines.map(line => line.split(/\t/).map(p => p.trim()));
      while (bodyEl.children.length < startRowIndex + rowsData.length) {
        bodyEl.appendChild(createRow());
      }
      rowsData.forEach((colsArr, i) => {
        const tr = bodyEl.children[startRowIndex + i];
        tr.classList.remove('example-row');
        const inputs = tr.querySelectorAll('input');
        colsArr.forEach((val, ci) => {
          const targetCol = focusedColIndex + ci;
          if (targetCol < inputs.length && val) inputs[targetCol].value = val;
        });
      });
    } else {
      // 한 열 데이터 — 포커스된 열에만 삽입
      const rowsData = lines.map(line => line.trim());
      while (bodyEl.children.length < startRowIndex + rowsData.length) {
        bodyEl.appendChild(createRow());
      }
      rowsData.forEach((val, i) => {
        const tr = bodyEl.children[startRowIndex + i];
        tr.classList.remove('example-row');
        const inputs = tr.querySelectorAll('input');
        if (val) inputs[focusedColIndex].value = val;
      });
    }

    renumber();
    ensureEmptyRows();
  });

  function init() {
    bodyEl.innerHTML = '';
    if (exampleValues) bodyEl.appendChild(createRow(exampleValues, true));
    for (let i = 0; i < 3; i++) bodyEl.appendChild(createRow());
    renumber();
  }

  // 예시 행을 제외한 실제 입력 행들의 값 배열 반환: [[c0, c1, ...], ...]
  function getRows() {
    return Array.from(bodyEl.querySelectorAll('tr'))
      .filter(tr => !tr.classList.contains('example-row'))
      .map(tr => Array.from(tr.querySelectorAll('input')).map(inp => inp.value.trim()));
  }

  function setRows(rows) {
    bodyEl.innerHTML = '';
    rows.forEach(r => bodyEl.appendChild(createRow(r)));
    ensureEmptyRows();
    renumber();
  }

  return { init, getRows, setRows, createRow, renumber };
}

// 두 개의 그리드 생성
const memberGrid = createGrid(
  document.getElementById('memberGridBody'),
  [{ placeholder: '이메일 입력' }, { placeholder: 'gpt번호' }],
  ['peter@gmail.com', 'gpt10@ablearn.kr']
);

const adminGrid = createGrid(
  document.getElementById('adminGridBody'),
  [{ placeholder: '관리자 이메일' }, { placeholder: '시작 (gpt1)' }, { placeholder: '끝 (gpt40)' }],
  ['manager@ablearn.kr', 'gpt1', 'gpt40']
);

// ============================================================
// GPT 계정 범위 파싱/확장
// ============================================================
// "gpt1@ablearn.kr" -> { prefix: "gpt", num: 1 }
function parseGptAccount(s) {
  if (!s) return null;
  const base = s.split('@')[0].trim();
  const m = base.match(/^([A-Za-z_\-]*?)(\d+)$/);
  if (!m) return null;
  return { prefix: m[1], num: parseInt(m[2], 10) };
}

// 시작~끝 계정 문자열을 그룹 이름 배열로 확장
function expandRange(startStr, endStr) {
  const a = parseGptAccount(startStr);
  if (!a) return { error: `계정 형식을 알 수 없습니다: "${startStr}"` };

  // 끝 계정이 비어있으면 시작 계정 1개만
  if (!endStr || !endStr.trim()) {
    return { groups: [a.prefix + a.num] };
  }

  const b = parseGptAccount(endStr);
  if (!b) return { error: `계정 형식을 알 수 없습니다: "${endStr}"` };
  if (a.prefix !== b.prefix) {
    return { error: `시작/끝 계정의 접두어가 다릅니다: "${a.prefix}" vs "${b.prefix}"` };
  }

  const lo = Math.min(a.num, b.num);
  const hi = Math.max(a.num, b.num);
  if (hi - lo > 500) return { error: `범위가 너무 큽니다 (${hi - lo + 1}개). 500개 이하로 나눠주세요.` };

  const groups = [];
  for (let n = lo; n <= hi; n++) groups.push(a.prefix + n);
  return { groups };
}

// ============================================================
// 모드 전환
// ============================================================
function setMode(mode) {
  currentMode = mode;
  const isMember = mode === 'member';
  modeMemberBtn.classList.toggle('active', isMember);
  modeAdminBtn.classList.toggle('active', !isMember);
  memberSection.style.display = isMember ? 'block' : 'none';
  adminSection.style.display = isMember ? 'none' : 'block';
}

modeMemberBtn.addEventListener('click', () => setMode('member'));
modeAdminBtn.addEventListener('click', () => setMode('admin'));

// ============================================================
// 초기화 버튼
// ============================================================
clearBtn.addEventListener('click', () => {
  memberGrid.init();
  adminGrid.init();
  statusDiv.innerText = '';
  logArea.innerHTML = '';
  startBtn.disabled = false;
});

// ============================================================
// 입력값 -> 작업(tasks) 목록 생성
// ============================================================
function buildTasks() {
  const tasks = [];

  if (currentMode === 'member') {
    memberGrid.getRows().forEach(([email, gpt]) => {
      if (!email || !gpt) return;
      tasks.push({ email, gpt: gpt.split('@')[0], role: 'member' });
    });
    return { tasks };
  }

  // 관리자 모드
  const rows = adminGrid.getRows();
  for (let i = 0; i < rows.length; i++) {
    const [email, startGpt, endGpt] = rows[i];
    if (!email && !startGpt && !endGpt) continue; // 완전 빈 행
    if (!email || !startGpt) {
      return { error: `${i + 1}행: 관리자 이메일과 시작 계정을 모두 입력해주세요.` };
    }
    const res = expandRange(startGpt, endGpt);
    if (res.error) return { error: `${i + 1}행: ${res.error}` };
    res.groups.forEach(g => tasks.push({ email, gpt: g, role: 'admin' }));
  }
  return { tasks };
}

// ============================================================
// 시작 버튼
// ============================================================
startBtn.addEventListener('click', () => {
  const built = buildTasks();
  if (built.error) {
    alert(built.error);
    return;
  }
  const tasks = built.tasks;

  if (tasks.length === 0) {
    alert('입력된 데이터가 없습니다.\n필요한 값을 모두 입력해주세요.');
    return;
  }

  const roleLabel = currentMode === 'admin' ? '관리자' : '회원';
  statusDiv.innerText = `총 ${tasks.length}건(${roleLabel}) 작업 시작...`;
  logArea.innerHTML = '';

  // 버튼/모드 상태 토글
  startBtn.style.display = 'none';
  stopBtn.style.display = 'inline-block';
  stopBtn.disabled = false;
  stopBtn.innerText = '■ 작업 중단';
  clearBtn.disabled = true;
  modeMemberBtn.disabled = true;
  modeAdminBtn.disabled = true;

  chrome.runtime.sendMessage({ action: "startJobs", tasks: tasks }, (response) => {
    startBtn.style.display = 'inline-block';
    startBtn.disabled = false;
    stopBtn.style.display = 'none';
    clearBtn.disabled = false;
    modeMemberBtn.disabled = false;
    modeAdminBtn.disabled = false;

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

// ============================================================
// 중단 버튼
// ============================================================
stopBtn.addEventListener('click', () => {
  stopBtn.disabled = true;
  stopBtn.innerText = '중단 중...';
  chrome.runtime.sendMessage({ action: "stopJobs" }, (response) => {
    if (response && response.status === "stopped") {
      statusDiv.innerText = "사용자 요청에 의해 작업을 중단하는 중입니다...";
      startBtn.style.display = 'inline-block';
      startBtn.disabled = false;
      stopBtn.style.display = 'none';
      stopBtn.innerText = '■ 작업 중단';
      clearBtn.disabled = false;
      modeMemberBtn.disabled = false;
      modeAdminBtn.disabled = false;
    }
  });
});

// ============================================================
// 진행 상태 수신
// ============================================================
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "updateStatus") {
    statusDiv.innerText = msg.text;
  } else if (msg.action === "logResult") {
    const div = document.createElement('div');
    div.innerText = msg.text;
    div.style.color = msg.text.includes('❌') ? '#d32f2f' : '#388e3c';
    logArea.appendChild(div);
    logArea.scrollTop = logArea.scrollHeight;
  }
});

// ============================================================
// 페이지 로드 시 상태 확인 및 초기화
// ============================================================
chrome.runtime.sendMessage({ action: "getRunningState" }, (response) => {
  if (response && response.isRunning) {
    startBtn.style.display = 'none';
    stopBtn.style.display = 'inline-block';
    stopBtn.disabled = false;
    stopBtn.innerText = '■ 작업 중단';
    clearBtn.disabled = true;
    modeMemberBtn.disabled = true;
    modeAdminBtn.disabled = true;

    memberGrid.init();
    adminGrid.init();

    // 실행 중인 작업이 관리자 작업이면 관리자 모드로 표시
    const tasks = response.tasks || [];
    const isAdminRun = tasks.some(t => t.role === 'admin');
    setMode(isAdminRun ? 'admin' : 'member');

    if (tasks.length > 0) {
      if (isAdminRun) {
        // 이미 개별 계정으로 확장된 상태 → 이메일 + 계정으로 표시
        adminGrid.setRows(tasks.map(t => [t.email, t.gpt, '']));
      } else {
        memberGrid.setRows(tasks.map(t => [t.email, t.gpt]));
      }
    }

    statusDiv.innerText = response.statusText;
    logArea.innerHTML = '';
    (response.logs || []).forEach(log => {
      const div = document.createElement('div');
      div.innerText = log.text;
      div.style.color = log.text.includes('❌') ? '#d32f2f' : '#388e3c';
      logArea.appendChild(div);
    });
    logArea.scrollTop = logArea.scrollHeight;
  } else {
    memberGrid.init();
    adminGrid.init();
    setMode('member');
  }
});
