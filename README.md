# Booking 酒店照片抓取工具

从 Booking.com 批量爬取酒店照片并下载到本地。

## 快速开始

```bash
# 1. 安装依赖
bash scripts/setup.sh

# 2. 一键抓取 + 下载
python3 src/download.py -q "大阪" --hotels 3 --headless

# 3. 查看结果
ls booking_photos/
```

## 分步使用

```bash
# 只抓链接
python3 src/fetch_urls.py -q "东京" --max-hotels 5 --headless -o urls.json

# 只下载
python3 src/download_photos.py -i urls.json -o ./booking_photos -w 3
```

## 参数说明

| 参数 | 含义 | 默认值 |
|------|------|--------|
| `-q` | 城市/酒店名 | 必填 |
| `-n / --hotels` | 最多几家 | 3 |
| `-p` | 搜索页数 | 1 |
| `-o` | 照片目录 | `./booking_photos` |
| `-w` | 下载并发 | 3 |
| `--headless` | 无界面浏览器 | false |
| `--size` | 图片尺寸 (thumb/medium/large/xlarge) | large |
| `--only-download` | 跳过抓 URL，只用已有 JSON 下载 | false |
| `--only-fetch` | 只抓 URL，不下载 | false |

## 架构

1. `src/fetch_urls.py` — Playwright 搜索 → 点「更多 N 张照片」→ 图库边滚边收集 URL → JSON
2. `src/download_photos.py` — 并发下载，跳过已存在文件
3. `src/download.py` — 一键封装（fetch + download）
4. `src/config.py` — 配置读取（config.json / 环境变量）

## 注意事项

- 首次运行需安装 Playwright Chromium（约 1–2 分钟）
- 单酒店约 1–2 分钟
- 下载并发建议 ≤ 5
- 遵守 Booking.com ToS
