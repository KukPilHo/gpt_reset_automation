import os
import shutil
import sys
import subprocess

def main():
    print("=========================================================")
    print("  GPT 계정 관리자 빌드 스크립트 (Python 기반)")
    print("=========================================================")
    
    # 1. PyInstaller 설치 확인
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller가 설치되어 있지 않습니다. 설치를 진행합니다...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        
    print("빌드를 시작합니다...")
    
    # 2. 기존 빌드 폴더 삭제 (클린 빌드)
    for folder in ["build", "dist"]:
        if os.path.exists(folder):
            shutil.rmtree(folder, ignore_errors=True)
            
    if os.path.exists("GPT_Manager.spec"):
        os.remove("GPT_Manager.spec")
        
    # 3. PyInstaller 명령어 구성 및 실행
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "GPT_Manager",
        "--noconsole",
        "--add-data", "static;static",
        "--add-data", "engines;engines",
        "--add-data", "utils;utils",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        "app.py"
    ]
    
    subprocess.check_call(cmd)
    
    print("=========================================================")
    print("빌드가 완료되었습니다!")
    print(r"실행 파일은 dist\GPT_Manager 디렉토리 내에 있습니다.")
    print(r"dist\GPT_Manager\GPT_Manager.exe 파일을 더블 클릭하여 실행할 수 있습니다.")
    print("=========================================================")

if __name__ == "__main__":
    main()
