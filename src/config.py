"""读取本地配置与环境变量（可选）"""
import json
import os
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "config.json"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_path(path: str) -> str:
    """支持 ~ 与相对路径，转为绝对路径"""
    return str(Path(path).expanduser().resolve())


def get_output_dir(cli_value: Optional[str] = None) -> str:
    """
    照片下载目录优先级:
      命令行 -o > 环境变量 BOOKING_OUTPUT_DIR > config.json output_dir > 默认
    """
    if cli_value is not None:
        return resolve_path(cli_value)
    env = os.environ.get("BOOKING_OUTPUT_DIR", "").strip()
    if env:
        return resolve_path(env)
    cfg = load_config().get("output_dir", "").strip()
    if cfg:
        return resolve_path(cfg)
    return resolve_path("./booking_photos")


def get_urls_file(cli_value: Optional[str] = None) -> str:
    if cli_value is not None:
        return resolve_path(cli_value)
    cfg = load_config().get("urls_file", "").strip()
    if cfg:
        return resolve_path(cfg)
    return resolve_path("./urls.json")
