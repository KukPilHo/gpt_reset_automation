#!/usr/bin/env bash

echo "========================================================="
echo "  GPT 계정 관리자 빌드 스크립트 (macOS 용)"
echo "========================================================="

# PyInstaller가 설치되어 있는지 확인
if ! command -v pyinstaller &> /dev/null
then
    echo "PyInstaller가 설치되어 있지 않습니다. 설치를 진행합니다..."
    pip3 install pyinstaller
fi

echo "빌드를 시작합니다..."

# 기존 빌드 폴더 삭제 (클린 빌드)
rm -rf build dist GPT_Manager.spec

# PyInstaller 실행
# --noconsole: 터미널 창 숨기기
# --add-data: 정적 파일 포함 (macOS: 콜론(:), Windows: 세미콜론(;))
pyinstaller --name "GPT_Manager" \
            --noconsole \
            --add-data "static:static" \
            --add-data "engines:engines" \
            --add-data "utils:utils" \
            --hidden-import "uvicorn.logging" \
            --hidden-import "uvicorn.loops" \
            --hidden-import "uvicorn.loops.auto" \
            --hidden-import "uvicorn.protocols" \
            --hidden-import "uvicorn.protocols.http" \
            --hidden-import "uvicorn.protocols.http.auto" \
            --hidden-import "uvicorn.protocols.websockets" \
            --hidden-import "uvicorn.protocols.websockets.auto" \
            --hidden-import "uvicorn.lifespan" \
            --hidden-import "uvicorn.lifespan.on" \
            app.py

echo "========================================================="
echo "빌드가 완료되었습니다!"
echo "실행 파일은 dist/GPT_Manager 디렉토리 내에 있습니다."
echo "dist/GPT_Manager/GPT_Manager 파일을 더블 클릭하여 실행할 수 있습니다."
echo "========================================================="
