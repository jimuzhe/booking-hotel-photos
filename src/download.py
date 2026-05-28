#!/usr/bin/env python3
"""
一键抓取 + 下载（推荐日常使用）

示例:
  python3 download.py -q "东京"
  python3 download.py -q "拉斯维加斯" -o ~/Pictures/booking
  cp config.example.json config.json   # 写一次默认下载目录

下载目录优先级: 命令行 -o > 环境变量 BOOKING_OUTPUT_DIR > config.json > ./booking_photos
"""
import argparse
import subprocess
import sys
from pathlib import Path

from config import get_output_dir, get_urls_file, CONFIG_FILE

# src/ 目录（本文件所在目录）
_SRC_DIR = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(
        description="Booking 酒店照片：抓链接 + 下载",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
常用组合:
  试跑 1 家:  %(prog)s -q "东京" --hotels 1 --headless
  默认 3 家:  %(prog)s -q "拉斯维加斯"
  只下载:     %(prog)s --only-download
  固定目录:  编辑 config.json 里的 output_dir
        """.strip(),
    )
    default_out = get_output_dir()
    default_urls = get_urls_file()
    p.add_argument("-q", "--query", help="搜索关键词（城市/酒店名）")
    p.add_argument("-p", "--pages", type=int, default=1, help="搜索页数，每页约25家 (默认: 1)")
    p.add_argument(
        "--hotels", "-n",
        type=int,
        default=3,
        metavar="N",
        help="最多处理酒店数 (默认: 3；0=不限制)",
    )
    p.add_argument(
        "-o", "--output",
        default=None,
        metavar="DIR",
        help=f"照片保存目录 (默认: {default_out})",
    )
    p.add_argument(
        "-i", "--urls-file",
        default=None,
        metavar="FILE",
        help=f"URL 列表 JSON (默认: {default_urls})",
    )
    p.add_argument("-w", "--workers", type=int, default=3, help="下载并发数 (默认: 3，建议勿太大)")
    p.add_argument("--headless", action="store_true", help="浏览器无界面运行")
    p.add_argument(
        "--size",
        choices=["thumb", "medium", "large", "xlarge"],
        default="large",
        help="图片尺寸 (默认: large)",
    )
    p.add_argument("--checkin", default="", help="入住 YYYY-MM-DD")
    p.add_argument("--checkout", default="", help="退房 YYYY-MM-DD")
    p.add_argument(
        "--only-download",
        action="store_true",
        help="跳过抓 URL，只用已有 JSON 下载",
    )
    p.add_argument(
        "--only-fetch",
        action="store_true",
        help="只抓 URL，不下载",
    )
    args = p.parse_args()
    args.output = get_output_dir(args.output)
    args.urls_file = get_urls_file(args.urls_file)

    if CONFIG_FILE.exists():
        print(f"配置: {CONFIG_FILE}")
    print(f"下载目录: {args.output}")
    print(f"URL 文件: {args.urls_file}\n")

    if args.only_download:
        if not args.urls_file:
            p.error("请指定 -i urls.json")
        return _run_download(args)

    if not args.query:
        p.error("请指定搜索词 -q，或使用 --only-download")

    print("=" * 60)
    print("步骤 1/2: 获取酒店图片链接")
    print("=" * 60)
    cmd_fetch = [
        sys.executable, str(_SRC_DIR / "fetch_urls.py"),
        "--query", args.query,
        "--pages", str(args.pages),
        "--output", args.urls_file,
        "--image-size", args.size,
        "--max-hotels", str(args.hotels),
    ]
    if args.headless:
        cmd_fetch.append("--headless")
    if args.checkin:
        cmd_fetch.extend(["--checkin", args.checkin])
    if args.checkout:
        cmd_fetch.extend(["--checkout", args.checkout])

    print("执行:", " ".join(cmd_fetch))
    if subprocess.run(cmd_fetch).returncode != 0:
        print("步骤 1 失败")
        return 1

    if args.only_fetch:
        print(f"\n已保存: {args.urls_file}")
        return 0

    print()
    return _run_download(args)


def _run_download(args) -> int:
    print("=" * 60)
    print("步骤 2/2: 下载照片")
    print("=" * 60)
    cmd_dl = [
        sys.executable, str(_SRC_DIR / "download_photos.py"),
        "--input", args.urls_file,
        "--output", args.output,
        "--workers", str(args.workers),
    ]
    print("执行:", " ".join(cmd_dl))
    return subprocess.run(cmd_dl).returncode


if __name__ == "__main__":
    raise SystemExit(main() or 0)
