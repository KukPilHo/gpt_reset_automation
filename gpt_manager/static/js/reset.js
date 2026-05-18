/**
 * 계정 초기화 탭 로직
 */

function setWorkers(value) {
  document.getElementById('reset-workers').value = value;
  document.querySelectorAll('.workers-toggle-btn').forEach(btn => {
    btn.classList.toggle('active', parseInt(btn.dataset.value) === value);
  });
}

function startReset() {
  const rangeInput = document.getElementById('reset-range').value.trim();
  if (!rangeInput) {
    alert('계정 범위를 입력해주세요. (예: 1~10, 12, 15~17)');
    return;
  }

  const maxWorkers = parseInt(document.getElementById('reset-workers').value) || 2;

  // UI 상태 변경
  const startBtn = document.getElementById('btn-start-reset');
  const stopBtn = document.getElementById('btn-stop-reset');
  startBtn.disabled = true;
  startBtn.innerHTML = '<div class="spinner"></div> 진행 중...';
  stopBtn.style.display = 'inline-flex';

  // 로그 카드 표시 및 초기화
  const logCard = document.getElementById('reset-log-card');
  logCard.style.display = 'block';
  document.getElementById('reset-log').innerHTML = '';
  document.getElementById('reset-results').classList.remove('visible');

  // 상태 배지 업데이트
  const badge = document.getElementById('reset-status-badge');
  badge.textContent = '진행 중';
  badge.className = 'status-badge running';

  // WebSocket으로 작업 시작 요청
  sendWS({
    action: 'start_reset',
    range: rangeInput,
    max_workers: maxWorkers
  });
}
