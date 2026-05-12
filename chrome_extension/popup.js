const gridBody = document.getElementById('gridBody');
const pasteArea = document.getElementById('pasteArea');
const startBtn = document.getElementById('startBtn');
const clearBtn = document.getElementById('clearBtn');
const statusDiv = document.getElementById('status');

// 새 행(tr) 생성 함수
function createRow(email = '', gpt = '') {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input type="text" value="${email}"></td>
    <td><input type="text" value="${gpt}"></td>
  `;
  return tr;
}

// 붙여넣기 처리
pasteArea.addEventListener('paste', (e) => {
  e.preventDefault();
  let pasteData = (e.clipboardData || window.clipboardData).getData('text');
  if (!pasteData) return;
  
  processPastedData(pasteData);
});

// 사용자가 직접 입력/수정할 때 처리
pasteArea.addEventListener('input', (e) => {
  const val = e.target.value;
  // 탭이나 줄바꿈이 포함된 경우에만 붙여넣기로 간주하고 처리
  if (val.includes('\n') || val.includes('\t')) {
    processPastedData(val);
  }
});

function processPastedData(data) {
  // 줄바꿈으로 행 분리
  const lines = data.split('\n').map(l => l.trim()).filter(l => l !== '');
  
  // 탭으로 열 분리 (엑셀/스프레드시트는 탭으로 구분됨)
  const rowsData = lines.map(line => {
    return line.split(/[\t]+/).map(p => p.trim()); 
  });

  // 기존 empty-state 또는 데이터 초기화
  gridBody.innerHTML = '';

  let validCount = 0;
  rowsData.forEach(cols => {
    // 최소 1개 이상 데이터가 있으면 추가 (이메일, gpt)
    let email = cols[0] || '';
    let gpt = cols[1] || '';
    
    // 만약 탭이 아니라 띄어쓰기로 복사된 경우 대응
    if (!gpt && email.includes(' ')) {
      const parts = email.split(/ +/);
      email = parts[0];
      gpt = parts[1];
    }

    if (email) {
      gridBody.appendChild(createRow(email, gpt));
      validCount++;
    }
  });
  
  if (validCount === 0) {
     gridBody.innerHTML = '<tr><td colspan="2" class="empty-state">유효한 데이터가 없습니다. 다시 붙여넣어주세요.</td></tr>';
  }

  // textarea 비우기 및 포커스 해제
  pasteArea.value = '';
  pasteArea.blur();
}

// 초기화 버튼 이벤트
clearBtn.addEventListener('click', () => {
  gridBody.innerHTML = '<tr><td colspan="2" class="empty-state">위 칸에 데이터를 붙여넣으면 표가 생성됩니다.</td></tr>';
  pasteArea.value = '';
  statusDiv.innerText = '';
  startBtn.disabled = false;
});

// 시작 버튼 이벤트
startBtn.addEventListener('click', () => {
  const tasks = [];
  const rows = gridBody.querySelectorAll('tr');
  
  rows.forEach(row => {
    if (row.querySelector('.empty-state')) return; // 비어있는 상태면 무시
    
    const inputs = row.querySelectorAll('input');
    if (inputs.length < 2) return;
    
    const email = inputs[0].value.trim();
    let gpt = inputs[1].value.trim();
    
    if (email && gpt) {
      // 실수로 gpt10@ablearn.kr 형태를 넣더라도 gpt10 만 추출
      gpt = gpt.split('@')[0];
      tasks.push({ email, gpt });
    }
  });

  if (tasks.length === 0) {
    alert("입력된 데이터가 없습니다. 이메일과 GPT 계정을 확인해주세요.");
    return;
  }

  statusDiv.innerText = `총 ${tasks.length}명 작업 시작...`;
  startBtn.disabled = true;

  // 백그라운드 스크립트로 작업 전달
  chrome.runtime.sendMessage({ action: "startJobs", tasks: tasks }, (response) => {
    if(response && response.status === "done") {
       statusDiv.innerText += "\n\n🎉 모든 작업이 끝났습니다!";
       startBtn.disabled = false;
    }
  });
});

// 진행 상태 업데이트 메시지 수신
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "updateStatus") {
    statusDiv.innerText = msg.text;
  }
});
