#!/usr/bin/env python3
"""
第二步：读取 hotel_urls.json，批量下载所有照片

用法:
  python download_photos.py --input hotel_urls.json --output ./photos
  python download_photos.py --input tokyo_urls.json --output ./tokyo_photos --workers 8
"""

import argparse
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

import requests

from config import get_output_dir

HOTEL_PHOTO_PATH_RE = re.compile(r"/xdata/images/hotel/", re.I)


def normalize_photo_url(url: str) -> str:
    """script 来源的 URL 常含 \\u0026，不修复会导致 401"""
    if not url:
        return url
    return (
        url.replace("\\u0026", "&")
        .replace("\\u003d", "=")
        .replace("\\/", "/")
    )


def is_valid_hotel_photo_url(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    lower = url.lower()
    if not HOTEL_PHOTO_PATH_RE.search(lower):
        return False
    if not re.search(r"\.(jpe?g|webp)(?:\?|$)", lower):
        return False
    blocked = (
        "/avatars/", "/static/img/", "/design-assets/",
        "images-flags", "/illustrations-", "/xphoto/",
        ".svg", ".ico", ".gif", ".png",
    )
    return not any(b in lower for b in blocked)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("download_photos")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.booking.com/",
}


def safe_filename(name: str, max_len: int = 80) -> str:
    import re
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:max_len]


def download_single_photo(args: Tuple[str, Path]) -> bool:
    """下载单张照片"""
    url, save_path = args
    url = normalize_photo_url(url)
    if save_path.exists():
        return True
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        logger.warning("下载失败 %s: %s", url[:80], e)
        return False


def run(input_file: str, output_dir: str, workers: int = 5):
    """主流程"""

    # 1. 读取 JSON
    data = json.loads(Path(input_file).read_text(encoding="utf-8"))
    hotels = data.get("hotels", [])
    total_photos = data.get("total_photos", 0)

    logger.info("=" * 60)
    logger.info("开始下载")
    logger.info("酒店数: %d", len(hotels))
    logger.info("照片总数: %d", total_photos)
    logger.info("并发数: %d", workers)
    logger.info("=" * 60)

    # 2. 准备下载任务
    tasks: List[Tuple[str, Path]] = []
    for hotel in hotels:
        name = hotel.get("name", "unknown")
        folder = safe_filename(name)
        save_dir = Path(output_dir) / folder

        # 保存元数据
        meta = {
            "name": name,
            "url": hotel.get("url", ""),
            "hotel_id": hotel.get("hotel_id", ""),
            "rating": hotel.get("rating", ""),
            "review_count": hotel.get("review_count", ""),
            "price": hotel.get("price", ""),
            "address": hotel.get("address", ""),
        }
        save_dir.mkdir(parents=True, exist_ok=True)
        (save_dir / "metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        for i, photo in enumerate(hotel.get("photos", []), 1):
            url = photo.get("url", "")
            if not url or not is_valid_hotel_photo_url(url):
                continue
            ext = "webp" if url.endswith(".webp") else "jpg"
            save_path = save_dir / f"{i:03d}.{ext}"
            tasks.append((url, save_path))

    logger.info("实际下载任务: %d", len(tasks))

    # 3. 并发下载
    success = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(download_single_photo, t): t for t in tasks}
        for i, future in enumerate(as_completed(futures), 1):
            if future.result():
                success += 1
            else:
                failed += 1
            if i % 20 == 0:
                logger.info("进度: %d/%d (成功:%d 失败:%d)", i, len(tasks), success, failed)

    logger.info("=" * 60)
    logger.info("下载完成！")
    logger.info("成功: %d", success)
    logger.info("失败: %d", failed)
    logger.info("保存至: %s", Path(output_dir).resolve())
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="批量下载酒店照片")
    parser.add_argument("--input", "-i", required=True, help="输入 JSON 文件")
    default_out = get_output_dir()
    parser.add_argument(
        "--output", "-o",
        default=None,
        help=f"输出目录 (默认: {default_out}，可用 config.json 或 BOOKING_OUTPUT_DIR)",
    )
    parser.add_argument("--workers", "-w", type=int, default=5, help="并发下载数")

    args = parser.parse_args()
    output = get_output_dir(args.output)
    print(f"下载目录: {output}")
    run(args.input, output, args.workers)


if __name__ == "__main__":
    main()
