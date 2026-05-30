/**
 * GPT 계정 추가 / 리셋 자동화 — 메인 앱 로직
 * WebSocket 연결 관리, 탭 라우팅, 설정 API
 */

let ws = null;
let wsReconnectTimer = null;
let currentPage = 'reset';
let startTime = null;

// ===== 탭 네비게이션 =====
function navigateTo(page) {
  currentPage = page;

  // 탭 버튼 활성화
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.page === page);
  });

  // 페이지 표시
  document.querySelectorAll('.page').forEach(p => {
    p.classList.toggle('active', p.id === `page-${page}`);
  });

  // 설정 페이지 진입 시 설정 로드
  if (page === 'settings') {
    loadSettings();
  }
}

// ===== WebSocket 연결 =====
function connectWS() {
  if (ws && ws.readyState === WebSocket.OPEN) return ws;

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => {
    console.log('WebSocket 연결됨');
    if (wsReconnectTimer) {
      clearTimeout(wsReconnectTimer);
      wsReconnectTimer = null;
    }
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    handleWSMessage(data);
  };

  ws.onclose = () => {
    console.log('WebSocket 연결 해제');
    wsReconnectTimer = setTimeout(connectWS, 3000);
  };

  ws.onerror = (err) => {
    console.error('WebSocket 오류:', err);
  };

  return ws;
}

function sendWS(data) {
  const socket = connectWS();
  if (socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(data));
  } else {
    // 연결이 아직 안 되었으면 열릴 때 전송
    socket.addEventListener('open', () => {
      socket.send(JSON.stringify(data));
    }, { once: true });
  }
}

// ===== WebSocket 메시지 핸들러 =====
function handleWSMessage(data) {
  switch (data.type) {
    case 'log':
      appendLog(data.tag, data.msg);
      break;
    case 'status':
      handleStatus(data);
      break;
    case 'complete':
      handleComplete(data.results);
      break;
    case 'error':
      showError(data.msg);
      break;
    case 'pong':
      break;
  }
}

// ===== 로그 추가 =====
function appendLog(tag, msg) {
  // 현재 활성 로그 뷰어 찾기
  const logId = currentPage === 'members' ? 'member-log' : 'reset-log';
  const logEl = document.getElementById(logId);
  if (!logEl) return;

  // 빈 상태 메시지 제거
  const empty = logEl.querySelector('.log-empty');
  if (empty) empty.remove();

  const line = document.createElement('div');
  line.className = 'log-line';
  line.innerHTML = `<span class="log-tag">[${escapeHtml(tag)}]</span> ${escapeHtml(msg)}`;
  logEl.appendChild(line);

  // 자동 스크롤
  logEl.scrollTop = logEl.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ===== 상태 처리 =====
function handleStatus(data) {
  if (data.status === 'running') {
    startTime = Date.now();

    if (data.needs_login) {
      // 멤버 추가: 로그인 프롬프트 표시
      document.getElementById('login-prompt').classList.add('visible');
    }
  }

  if (data.status === 'stopped') {
    resetUI();
    appendLog('시스템', '🛑 작업이 중단되었습니다.');
  }
}

// ===== 완료 처리 =====
function handleComplete(results) {
  const elapsed = startTime ? Math.round((Date.now() - startTime) / 1000) : 0;
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const timeStr = minutes > 0 ? `${minutes}분 ${seconds}초` : `${seconds}초`;

  let okCount = 0;
  let failCount = 0;

  if (currentPage === 'reset') {
    okCount = results.filter(r => r.status === 'OK').length;
    failCount = results.filter(r => r.status !== 'OK').length;

    const resultsBar = document.getElementById('reset-results');
    resultsBar.classList.add('visible');
    document.querySelector('#reset-ok strong').textContent = okCount;
    document.querySelector('#reset-fail strong').textContent = failCount;
    document.querySelector('#reset-time strong').textContent = timeStr;

    document.getElementById('reset-status-badge').textContent = '완료';
    document.getElementById('reset-status-badge').className = 'status-badge idle';
  } else if (currentPage === 'members') {
    okCount = results.filter(r => r.status === 'OK' || r.status === 'ALREADY_EXISTS').length;
    failCount = results.filter(r => r.status === 'FAIL').length;

    const resultsBar = document.getElementById('member-results');
    resultsBar.classList.add('visible');
    document.querySelector('#member-ok strong').textContent = okCount;
    document.querySelector('#member-fail strong').textContent = failCount;

    document.getElementById('member-status-badge').textContent = '완료';
    document.getElementById('member-status-badge').className = 'status-badge idle';
  }

  resetUI();
  appendLog('시스템', '🎉 모든 작업이 완료되었습니다!');
  
  // 모달 띄우기
  const modal = document.getElementById('completion-modal');
  document.getElementById('modal-success').textContent = okCount;
  document.getElementById('modal-fail').textContent = failCount;
  modal.classList.add('visible');
}

// ===== 모달 닫기 =====
function closeModal() {
  document.getElementById('completion-modal').classList.remove('visible');
}

// ===== 에러 표시 =====
function showError(msg) {
  alert('⚠️ ' + msg);
  resetUI();
}

// ===== UI 리셋 =====
function resetUI() {
  // 시작 버튼 활성화
  document.querySelectorAll('[id^="btn-start-"]').forEach(btn => {
    btn.disabled = false;
    btn.innerHTML = btn.id.includes('reset')
      ? '▶ 초기화 시작'
      : '▶ 순차적 자동 추가 시작';
  });

  // 중지 버튼 숨기기
  document.querySelectorAll('[id^="btn-stop-"]').forEach(btn => {
    btn.style.display = 'none';
    btn.disabled = false;
    btn.innerHTML = '■ 중지';
  });

  // 로그인 프롬프트 숨기기
  document.getElementById('login-prompt').classList.remove('visible');
}

// ===== 작업 중지 =====
function stopTask() {
  document.querySelectorAll('[id^="btn-stop-"]').forEach(btn => {
    btn.disabled = true;
    btn.innerHTML = '중지 중...';
  });

  sendWS({ action: 'stop' });
  fetch('/api/stop', { method: 'POST' });
}

// ===== 로그인 완료 확인 =====
function confirmLogin() {
  sendWS({ action: 'login_complete' });
  fetch('/api/login-complete', { method: 'POST' });
  document.getElementById('login-prompt').classList.remove('visible');
  appendLog('시스템', '✅ 로그인 확인 — 자동 추가를 시작합니다.');
}

// ===== 설정 관련 =====
async function loadSettings() {
  try {
    const res = await fetch('/api/config');
    const config = await res.json();
    document.getElementById('cfg-master-email').value = config.master_email || '';
    document.getElementById('cfg-app-password').value = config.app_password || '';
    document.getElementById('cfg-common-password').value = config.common_password || '';
  } catch (e) {
    console.error('설정 로드 실패:', e);
  }
}

async function saveSettings() {
  const data = {
    master_email: document.getElementById('cfg-master-email').value.trim(),
    app_password: document.getElementById('cfg-app-password').value.trim(),
    common_password: document.getElementById('cfg-common-password').value.trim()
  };

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    const result = await res.json();
    const statusEl = document.getElementById('settings-status');
    statusEl.innerHTML = '<span style="color:var(--success);">✅ 설정이 저장되었습니다.</span>';
    setTimeout(() => { statusEl.innerHTML = ''; }, 3000);
  } catch (e) {
    const statusEl = document.getElementById('settings-status');
    statusEl.innerHTML = '<span style="color:var(--error);">❌ 저장 실패: ' + e.message + '</span>';
  }
}

function togglePassword(inputId, btn) {
  const input = document.getElementById(inputId);
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🔒';
  } else {
    input.type = 'password';
    btn.textContent = '👁';
  }
}

// ===== 초기화 =====
document.addEventListener('DOMContentLoaded', () => {
  connectWS();
});
