const gridBody = document.getElementById('gridBody');

// 새 행(tr) 생성 함수
function createRow(email = '', gpt = '') {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input type="text" value="${email}"></td>
    <td><input type="text" value="${gpt}"></td>
  `;
  return tr;
}

// 줄 추가 버튼 이벤트
document.getElementById('addRowBtn').addEventListener('click', () => {
  gridBody.appendChild(createRow());
});

// 초기화 버튼 이벤트
document.getElementById('clearBtn').addEventListener('click', () => {
  gridBody.innerHTML = '';
  for(let i=0; i<3; i++) gridBody.appendChild(createRow());
});

// 🌟 핵심: 엑셀에서 복사한 데이터 붙여넣기(Paste) 자동 처리
gridBody.addEventListener('paste', (e) => {
  e.preventDefault();
  let pasteData = (e.clipboardData || window.clipboardData).getData('text');
  if (!pasteData) return;
  
  // 줄바꿈으로 행 분리
  const lines = pasteData.split('\n').map(l => l.trim()).filter(l => l !== '');
  
  // 현재 커서가 있는 행(Row) 위치 파악
  let targetInput = e.target;
  let startRowIndex = 0;
  if (targetInput && targetInput.tagName === 'INPUT') {
    let tr = targetInput.closest('tr');
    startRowIndex = Array.from(gridBody.children).indexOf(tr);
  }

  // 탭이나 띄어쓰기로 열(Column) 분리
  const rowsData = lines.map(line => {
    return line.split(/[\t\s]+/).filter(p => p.trim() !== '');
  });

  // 복사한 데이터의 줄 수만큼 표(그리드) 행 개수 늘리기
  while(gridBody.children.length < startRowIndex + rowsData.length) {
    gridBody.appendChild(createRow());
  }

  // 늘어난 표에 데이터 꽂아넣기
  rowsData.forEach((cols, i) => {
    let tr = gridBody.children[startRowIndex + i];
    let inputs = tr.querySelectorAll('input');
    if(cols[0]) inputs[0].value = cols[0];
    if(cols[1]) inputs[1].value = cols[1];
  });
});

// 시작 버튼 이벤트
document.getElementById('startBtn').addEventListener('click', () => {
  const tasks = [];
  const rows = gridBody.querySelectorAll('tr');
  
  // 표의 모든 값을 순회하며 데이터 수집
  rows.forEach(row => {
    const inputs = row.querySelectorAll('input');
    const email = inputs[0].value.trim();
    let gpt = inputs[1].value.trim();
    
    if (email && gpt) {
      // 실수로 gpt10@ablearn.kr 형태를 넣더라도 gpt10 만 추출
      gpt = gpt.split('@')[0];
      tasks.push({ email, gpt });
    }
  });

  if (tasks.length === 0) return alert("입력된 데이터가 없습니다. 이메일과 그룹ID를 확인해주세요.");

  document.getElementById('status').innerText = `총 ${tasks.length}명 작업 시작...`;
  document.getElementById('startBtn').disabled = true;

  // 백그라운드 스크립트로 작업 전달
  chrome.runtime.sendMessage({ action: "startJobs", tasks: tasks }, (response) => {
    if(response && response.status === "done") {
       document.getElementById('status').innerText += "\n\n🎉 모든 작업이 끝났습니다!";
       document.getElementById('startBtn').disabled = false;
    }
  });
});

// 진행 상태 업데이트 메시지 수신
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.action === "updateStatus") {
    document.getElementById('status').innerText = msg.text;
  }
});
