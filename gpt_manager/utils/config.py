import json
import os
import base64

# config.json 경로: 실행 파일과 같은 디렉토리
def _get_config_path():
    """실행 파일 기준으로 config.json 경로를 반환합니다."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "config.json")

DEFAULT_CONFIG = {
    "master_email": "",
    "app_password": "",
    "common_password": "",
    "max_workers": 2
}


def load_config():
    """config.json에서 설정을 로드합니다."""
    config_path = _get_config_path()
    if not os.path.exists(config_path):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    # 비밀번호 디코딩 (base64 난독화)
    for key in ["app_password", "common_password"]:
        if config.get(key):
            try:
                config[key] = base64.b64decode(config[key]).decode()
            except Exception:
                pass  # 이미 평문이면 그대로 사용

    return config


def save_config(config):
    """설정을 config.json에 저장합니다."""
    config_path = _get_config_path()
    save_data = config.copy()

    # 비밀번호 인코딩 (base64 난독화)
    for key in ["app_password", "common_password"]:
        if save_data.get(key):
            try:
                # 이미 base64인지 확인
                base64.b64decode(save_data[key])
            except Exception:
                save_data[key] = base64.b64encode(save_data[key].encode()).decode()

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)


def is_config_valid(config):
    """필수 설정값이 모두 입력되어 있는지 확인합니다."""
    return bool(
        config.get("master_email")
        and config.get("app_password")
        and config.get("common_password")
    )


def parse_ranges(range_str):
    """'1~10, 12, 15~17' 형식의 문자열을 정수 리스트로 변환합니다."""
    numbers = []
    parts = [p.strip() for p in range_str.split(',')]
    for part in parts:
        if not part:
            continue
        if '~' in part:
            try:
                start_str, end_str = part.split('~')
                start = int(start_str)
                end = int(end_str)
                numbers.extend(range(start, end + 1))
            except ValueError:
                pass
        else:
            try:
                numbers.append(int(part))
            except ValueError:
                pass
    return sorted(list(set(numbers)))
