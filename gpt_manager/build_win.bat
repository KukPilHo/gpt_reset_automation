@echo off
echo =========================================================
echo   GPT 계정 관리자 빌드 스크립트 (Windows 용)
echo =========================================================

:: PyInstaller 설치 확인
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller가 설치되어 있지 않습니다. 설치를 진행합니다...
    pip install pyinstaller
)

echo 빌드를 시작합니다...

:: 기존 빌드 폴더 삭제 (클린 빌드)
rmdir /s /q build
rmdir /s /q dist
del /q GPT_Manager.spec

:: PyInstaller 실행
:: --noconsole: 터미널 창 숨기기
:: --add-data: 정적 파일 포함 (Windows는 세미콜론(;) 사용)
pyinstaller --name "GPT_Manager" ^
            --noconsole ^
            --add-data "static;static" ^
            --add-data "engines;engines" ^
            --add-data "utils;utils" ^
            --hidden-import "uvicorn.logging" ^
            --hidden-import "uvicorn.loops" ^
            --hidden-import "uvicorn.loops.auto" ^
            --hidden-import "uvicorn.protocols" ^
            --hidden-import "uvicorn.protocols.http" ^
            --hidden-import "uvicorn.protocols.http.auto" ^
            --hidden-import "uvicorn.protocols.websockets" ^
            --hidden-import "uvicorn.protocols.websockets.auto" ^
            --hidden-import "uvicorn.lifespan" ^
            --hidden-import "uvicorn.lifespan.on" ^
            app.py

echo =========================================================
echo 빌드가 완료되었습니다!
echo 실행 파일은 dist\GPT_Manager 디렉토리 내에 있습니다.
echo dist\GPT_Manager\GPT_Manager.exe 파일을 더블 클릭하여 실행할 수 있습니다.
echo =========================================================
pause
