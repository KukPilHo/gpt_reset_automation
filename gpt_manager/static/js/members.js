/**
 * 멤버 추가 탭 로직
 * 기존 chrome_extension/popup.js의 엑셀 그리드 로직을 그대로 재사용합니다.
 */

const memberGrid = document.getElementById('member-grid');

// ===== 행(Row) 생성 (크롬 확장 popup.js 그대로) =====
function createRow(email = '', gpt = '', isExample = false) {
  const tr = document.createElement('tr');
  if (isExample) tr.classList.add('example-row');

  const rowNum = memberGrid.children.length + 1;
  tr.innerHTML = `
    <td class="row-num">${rowNum}</td>
    <td><input type="text" value="${escapeHtml(email)}" placeholder="${isExample ? '' : '이메일 입력'}"></td>
    <td><input type="text" value="${escapeHtml(gpt)}" placeholder="${isExample ? '' : 'gpt번호'}"></td>
  `;

  tr.querySelectorAll('input').forEach(input => {
    input.addEventListener('input', onCellInput);
    input.addEventListener('focus', onCellFocus);
  });

  return tr;
}

// ===== 행 번호 재정렬 =====
function renumberRows() {
  Array.from(memberGrid.children).forEach((tr, i) => {
    const numCell = tr.querySelector('.row-num');
    if (numCell) numCell.textContent = i + 1;
  });
}

// ===== 빈 행 자동 추가 =====
function ensureEmptyRows() {
  const rows = Array.from(memberGrid.children);
  let emptyTailCount = 0;
  for (let i = rows.length - 1; i >= 0; i--) {
    const inputs = rows[i].querySelectorAll('input');
    if (!inputs.length) break;
    const email = inputs[0].value.trim();
    const gpt = inputs[1].value.trim();
    if (!email && !gpt) {
      emptyTailCount++;
    } else {
      break;
    }
  }
  if (emptyTailCount < 1) {
    memberGrid.appendChild(createRow());
    renumberRows();
  }
}

function onCellInput(e) {
  const tr = e.target.closest('tr');
  if (tr) tr.classList.remove('example-row');
  ensureEmptyRows();
}

function onCellFocus(e) {
  const tr = e.target.closest('tr');
  if (tr && tr.classList.contains('example-row')) {
    e.target.select();
  }
}

// ===== 붙여넣기 처리 (셀에서 ⌘+V) =====
memberGrid.addEventListener('paste', (e) => {
  const pasteData = (e.clipboardData || window.clipboardData).getData('text');
  if (!pasteData) return;

  if (!pasteData.includes('\n') && !pasteData.includes('\t')) return;

  e.preventDefault();

  const lines = pasteData.split('\n').map(l => l.trim()).filter(l => l !== '');
  const rowsData = lines.map(line => {
    if (line.includes('\t')) {
      return line.split(/\t+/).map(p => p.trim());
    }
    return line.split(/\s+/).map(p => p.trim());
  });

  let targetInput = e.target;
  let startRowIndex = 0;
  if (targetInput && targetInput.tagName === 'INPUT') {
    const tr = targetInput.closest('tr');
    startRowIndex = Array.from(memberGrid.children).indexOf(tr);
    if (startRowIndex < 0) startRowIndex = 0;
  }

  while (memberGrid.children.length < startRowIndex + rowsData.length) {
    memberGrid.appendChild(createRow());
  }

  rowsData.forEach((cols, i) => {
    const tr = memberGrid.children[startRowIndex + i];
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
  memberGrid.innerHTML = '';
  memberGrid.appendChild(createRow('peter@gmail.com', 'gpt10@ablearn.kr', true));
  for (let i = 0; i < 4; i++) {
    memberGrid.appendChild(createRow());
  }
  renumberRows();
}

function clearMemberData() {
  initGrid();
  document.getElementById('member-log').innerHTML = '';
  document.getElementById('member-log-card').style.display = 'none';
  document.getElementById('member-results').classList.remove('visible');
  document.getElementById('login-prompt').classList.remove('visible');
}

// ===== 멤버 추가 시작 =====
function startMembers() {
  const tasks = [];
  const rows = memberGrid.querySelectorAll('tr');

  rows.forEach(row => {
    if (row.classList.contains('example-row')) return;
    const inputs = row.querySelectorAll('input');
    if (inputs.length < 2) return;

    const email = inputs[0].value.trim();
    let gpt = inputs[1].value.trim();

    if (!email || !gpt) return;
    gpt = gpt.split('@')[0];
    tasks.push({ email, gpt });
  });

  if (tasks.length === 0) {
    alert('입력된 데이터가 없습니다.\n이메일과 GPT 계정을 모두 입력해주세요.');
    return;
  }

  const startBtn = document.getElementById('btn-start-members');
  const stopBtn = document.getElementById('btn-stop-members');
  startBtn.disabled = true;
  startBtn.innerHTML = '<div class="spinner"></div> 진행 중...';
  stopBtn.style.display = 'inline-flex';

  document.getElementById('member-log-card').style.display = 'block';
  document.getElementById('member-log').innerHTML = '';
  document.getElementById('member-results').classList.remove('visible');

  const badge = document.getElementById('member-status-badge');
  badge.textContent = '진행 중';
  badge.className = 'status-badge running';

  sendWS({
    action: 'start_members',
    tasks: tasks
  });
}

// ===== 페이지 로드 시 그리드 초기화 =====
document.addEventListener('DOMContentLoaded', initGrid);
