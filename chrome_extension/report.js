document.addEventListener('DOMContentLoaded', () => {
  chrome.storage.local.get(['gptAutoResults'], (data) => {
    if (!data.gptAutoResults) {
      document.body.innerHTML = '<div style="padding: 40px; text-align: center;">결과 데이터를 찾을 수 없습니다.</div>';
      return;
    }

    const { elapsedTime, successCount, failCount, jobResults } = data.gptAutoResults;

    // 요약 카드 업데이트
    const minutes = Math.floor(elapsedTime / 60);
    const seconds = elapsedTime % 60;
    const timeStr = minutes > 0 ? `${minutes}분 ${seconds}초` : `${seconds}초`;
    
    document.getElementById('elapsedTime').textContent = timeStr;
    document.getElementById('successCount').textContent = `${successCount}건`;
    document.getElementById('failCount').textContent = `${failCount}건`;

    const failTable = document.getElementById('failTable');
    const failTableBody = document.getElementById('failTableBody');
    const noFailMessage = document.getElementById('noFailMessage');
    const allTableBody = document.getElementById('allTableBody');

    // 실패한 항목만 필터링
    const failedJobs = jobResults.filter(job => job.status === 'FAIL');
    
    if (failedJobs.length > 0) {
      failTable.style.display = 'table';
      noFailMessage.style.display = 'none';
      
      failedJobs.forEach(job => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${job.email}</strong></td>
          <td>${job.gpt}</td>
          <td class="reason">${job.reason || '알 수 없는 오류'}</td>
        `;
        failTableBody.appendChild(tr);
      });
    }

    // 전체 리스트
    jobResults.forEach(job => {
      const tr = document.createElement('tr');
      const isSuccess = job.status === 'OK';
      tr.innerHTML = `
        <td><span class="badge ${isSuccess ? 'success' : 'fail'}">${isSuccess ? '성공' : '실패'}</span></td>
        <td>${job.email}</td>
        <td>${job.gpt}</td>
        <td><span style="font-size:12px; color:#5f6368;">${job.reason || '-'}</span></td>
      `;
      allTableBody.appendChild(tr);
    });

    // 재시도 버튼 로직
    const retryBtn = document.getElementById('retryBtn');
    if (failedJobs.length > 0) {
      retryBtn.style.display = 'inline-block';
      retryBtn.textContent = `❌ 실패 항목 ${failedJobs.length}건 재시도`;
      
      retryBtn.addEventListener('click', () => {
        // 백그라운드 스크립트가 처리할 수 있는 형식 {email, gpt}으로 변환
        const retryTasks = failedJobs.map(job => ({ email: job.email, gpt: job.gpt }));
        
        retryBtn.disabled = true;
        retryBtn.textContent = '재시도 시작 중...';
        
        chrome.runtime.sendMessage({ action: "startJobs", tasks: retryTasks }, (response) => {
          alert('재시도를 백그라운드에서 시작했습니다!\n창을 닫으셔도 되며, 작업이 끝나면 새로운 리포트가 뜹니다.');
          window.close();
        });
      });
    }

    // 확인했으면 스토리지에서 삭제(초기화)
    chrome.storage.local.remove('gptAutoResults');
  });
});
