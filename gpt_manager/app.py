"""
GPT 계정 추가 / 리셋 자동화 — 메인 서버
FastAPI 기반 로컬 웹 서버. 브라우저에서 웹 UI를 제공하고 WebSocket으로 실시간 로그를 스트리밍합니다.
"""
import os
import sys
import json
import asyncio
import threading
import webbrowser
from queue import Queue, Empty

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.config import load_config, save_config, is_config_valid, parse_ranges
from engines.reset_engine import run_reset
from engines.member_engine import run_add_members

app = FastAPI(title="GPT 계정 추가 / 리셋 자동화")

# 정적 파일 서빙
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 글로벌 상태
stop_event = threading.Event()
login_event = threading.Event()
is_running = False


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/config")
async def get_config():
    config = load_config()
    # 비밀번호는 마스킹하여 전달
    safe_config = config.copy()
    for key in ["app_password", "common_password"]:
        if safe_config.get(key):
            safe_config[key] = "●" * 8
    safe_config["is_valid"] = is_config_valid(config)
    return JSONResponse(safe_config)


@app.post("/api/config")
async def update_config(data: dict):
    current = load_config()
    # 마스킹된 값("●●●●●●●●")이면 기존 값 유지
    for key in ["master_email", "app_password", "common_password", "max_workers"]:
        if key in data:
            if isinstance(data[key], str) and "●" in data[key]:
                continue  # 마스킹된 값은 무시
            current[key] = data[key]
    save_config(current)
    return JSONResponse({"status": "ok"})


@app.post("/api/stop")
async def stop_task():
    global stop_event
    stop_event.set()
    return JSONResponse({"status": "stopped"})


@app.post("/api/login-complete")
async def login_complete():
    global login_event
    login_event.set()
    return JSONResponse({"status": "ok"})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global is_running, stop_event, login_event
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "start_reset":
                await handle_reset(websocket, data)
            elif action == "start_members":
                await handle_members(websocket, data)
            elif action == "stop":
                stop_event.set()
                await websocket.send_json({"type": "status", "status": "stopped"})
            elif action == "login_complete":
                login_event.set()
            elif action == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        stop_event.set()
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "msg": str(e)})
        except:
            pass


async def handle_reset(websocket: WebSocket, data: dict):
    global is_running, stop_event

    if is_running:
        await websocket.send_json({"type": "error", "msg": "이미 작업이 진행 중입니다."})
        return

    config = load_config()
    if not is_config_valid(config):
        await websocket.send_json({"type": "error", "msg": "설정을 먼저 완료해주세요. (설정 탭에서 이메일/비밀번호 입력)"})
        return

    range_str = data.get("range", "")
    target_numbers = parse_ranges(range_str)
    if not target_numbers:
        await websocket.send_json({"type": "error", "msg": "유효한 계정 번호가 없습니다."})
        return

    max_workers = min(int(data.get("max_workers", config.get("max_workers", 2))), 3)

    is_running = True
    stop_event = threading.Event()
    log_queue = Queue()
    loop = asyncio.get_event_loop()

    def log_callback(tag, msg):
        log_queue.put({"type": "log", "tag": tag, "msg": msg})

    def work():
        try:
            return run_reset(target_numbers, max_workers, config, log_callback, stop_event)
        except Exception as e:
            log_callback("시스템", f"❌ 치명적 오류: {e}")
            return [{"status": "FAIL", "reason": str(e)}]

    await websocket.send_json({"type": "status", "status": "running"})

    future = loop.run_in_executor(None, work)

    try:
        while not future.done():
            # 로그 큐에서 메시지 전송
            while not log_queue.empty():
                try:
                    item = log_queue.get_nowait()
                    await websocket.send_json(item)
                except Empty:
                    break
            await asyncio.sleep(0.3)

        # 남은 로그 전송
        await asyncio.sleep(0.5)
        while not log_queue.empty():
            try:
                item = log_queue.get_nowait()
                await websocket.send_json(item)
            except Empty:
                break

        results = future.result()
        await websocket.send_json({"type": "complete", "results": results})
    except Exception as e:
        await websocket.send_json({"type": "error", "msg": str(e)})
    finally:
        is_running = False


async def handle_members(websocket: WebSocket, data: dict):
    global is_running, stop_event, login_event

    if is_running:
        await websocket.send_json({"type": "error", "msg": "이미 작업이 진행 중입니다."})
        return

    tasks = data.get("tasks", [])
    if not tasks:
        await websocket.send_json({"type": "error", "msg": "입력된 데이터가 없습니다."})
        return

    is_running = True
    stop_event = threading.Event()
    login_event = threading.Event()
    log_queue = Queue()
    loop = asyncio.get_event_loop()

    def log_callback(tag, msg):
        log_queue.put({"type": "log", "tag": tag, "msg": msg})

    def work():
        try:
            return run_add_members(tasks, log_callback, login_event, stop_event)
        except Exception as e:
            log_callback("시스템", f"❌ 치명적 오류: {e}")
            return [{"status": "FAIL", "reason": str(e)}]

    await websocket.send_json({"type": "status", "status": "running", "needs_login": True})

    future = loop.run_in_executor(None, work)

    try:
        while not future.done():
            # 클라이언트 메시지 확인 (login_complete, stop 등)
            try:
                client_msg = await asyncio.wait_for(websocket.receive_json(), timeout=0.1)
                if client_msg.get("action") == "login_complete":
                    login_event.set()
                elif client_msg.get("action") == "stop":
                    stop_event.set()
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                stop_event.set()
                break

            # 로그 큐에서 메시지 전송
            while not log_queue.empty():
                try:
                    item = log_queue.get_nowait()
                    await websocket.send_json(item)
                except Empty:
                    break

            await asyncio.sleep(0.2)

        # 남은 로그 전송
        await asyncio.sleep(0.5)
        while not log_queue.empty():
            try:
                item = log_queue.get_nowait()
                await websocket.send_json(item)
            except Empty:
                break

        results = future.result()
        await websocket.send_json({"type": "complete", "results": results})
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "msg": str(e)})
        except:
            pass
    finally:
        is_running = False


def main():
    PORT = 8080
    print("=========================================================")
    print("  GPT 계정 추가 / 리셋 자동화")
    print(f"  http://localhost:{PORT}")
    print("=========================================================")

    # 브라우저 자동 열기 (약간의 지연 후)
    def open_browser():
        import time
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{PORT}")

    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
