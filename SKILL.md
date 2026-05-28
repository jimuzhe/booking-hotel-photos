---
name: booking-hotel-photos
version: 2.0.0
description: >-
  Batch scrape and download hotel photos from Booking.com (Playwright + requests).
  Use when the user wants to download/save/scrape hotel photos from Booking.com,
  or mentions booking hotel images, 酒店照片, 抓取 booking 图片, booking_photos,
  hotel gallery download, or specifies a city/hotel name for photo scraping.
  Supports: city/hotel name search, configurable hotel count, image size selection,
  output directory, concurrent download workers, fetch-only and download-only modes.
metadata:
  requires:
    bins: ["python3"]
---

# Booking 酒店照片抓取

从 Booking.com 批量爬取酒店照片并下载到本地。

## 参数提取规则

从用户对话中提取以下参数（未提及的使用默认值）：

| 参数 | 提取规则 | 默认值 |
|------|---------|--------|
| `query` | 城市名或酒店名（必填，用户未提供时主动询问） | — |
| `hotels` | 数字 + "家" → 该数字 | `3` |
| `size` | "大/大图/large" → `large`；"超大/xlarge" → `xlarge`；"中/medium" → `medium`；"缩略/thumb" → `thumb` | `large` |
| `output` | "到/保存到/下载到 + 路径" → 该路径 | `./booking_photos` |
| `workers` | "并发 + 数字" → 该数字 | `3` |
| `pages` | "第 N 页" 或 "翻 N 页" → 该数字 | `1` |
| `only_fetch` | "只抓链接/只获取URL/不下载" → `true` | `false` |
| `only_download` | "只下载/用已有链接下载" → `true` | `false` |
| `urls_file` | "用/从 + 文件名" → 该文件路径 | `./urls.json` |
| `headless` | "无界面/后台" → `true` | `true` |

### 提取示例

- "帮我爬大阪 3 家酒店的图片" → `query=大阪, hotels=3`
- "下载东京 5 家酒店的大图到 ~/Pictures" → `query=东京, hotels=5, size=large, output=~/Pictures`
- "只抓拉斯维加斯的链接不下载" → `query=拉斯维加斯, only_fetch=true`
- "用已有的 urls.json 下载" → `only_download=true`
- "抓 10 家酒店，并发 5" → `hotels=10, workers=5`

## 执行流程

### Step 0：安装依赖（每次任务必须先做）

**不要等用户开口——skill 触发后必须先执行本节。**

SKILL_DIR 为 skill 所在目录（即本 SKILL.md 的上级目录）。

```bash
SKILL_DIR="<skill 目录绝对路径>"
cd "$SKILL_DIR"

python3 -m pip install -r requirements.txt
python3 -m playwright install chromium
test -f config.json || cp config.example.json config.json
```

自检：`python3 -c "import playwright, requests; print('deps ok')"`

首次安装约 1–2 分钟。完成后告知用户「依赖已就绪」，再继续。

### Step 1：构建命令

使用 `src/download.py` 一键执行（fetch + download）：

```bash
cd "$SKILL_DIR"
python3 src/download.py -q "<query>" --hotels <N> --size <size> -o <output> -w <workers> --headless
```

或分步执行：

```bash
# 只抓链接
python3 src/fetch_urls.py -q "<query>" --max-hotels <N> --image-size <size> --headless -i <urls_file>

# 只下载
python3 src/download_photos.py -i <urls_file> -o <output> -w <workers>
```

### Step 2：执行并监控

- 单酒店约 1–2 分钟，总时长 ≈ 酒店数 × 2 分钟
- 下载并发 ≤ 5
- 长任务设置足够超时（建议 600000ms）

### Step 3：完成后汇报

必须包含：
- 搜索词、酒店数、照片总数
- 输出目录绝对路径
- urls.json 绝对路径
- 下载成功/失败数

## 错误处理

| 情况 | 处理 |
|------|------|
| Playwright 未安装 | 自动执行 `python3 -m playwright install chromium` |
| 搜索页加载失败 | 重试 3 次，仍失败则报错并告知用户 |
| 某酒店图片获取失败 | 跳过该酒店，继续其余，最终汇报失败的酒店名 |
| 下载失败 | 记录失败 URL，最终汇报失败数 |
| 依赖安装失败 | 告知用户手动运行 `pip install -r requirements.txt && playwright install chromium` |

## 约束

- 遵守 Booking.com ToS
- 下载并发 ≤ 5
- 每次请求随机延迟 1.5–3s

## 参考

- `reference.md` — 技术架构说明
