# Booking 酒店照片抓取工具

从 Booking.com 批量爬取酒店照片并下载到本地。

## 安装（给别人用）

### 给 AI 的一句话安装指令（Claude Code / Cursor Agent）

把下面这句话直接发给 AI，它会在终端执行安装：

```bash
请在终端执行：git clone https://github.com/jimuzhe/booking-hotel-photos.git ~/.claude/skills/booking-hotel-photos && cd ~/.claude/skills/booking-hotel-photos && bash install.sh
```

安装完成后可让 AI 继续执行验证：

```bash
请在终端执行：python3 -c "import playwright, requests; print('deps ok')"
```

### 方式一：一键安装（推荐）

```bash
git clone <仓库地址> booking-hotel-photos
cd booking-hotel-photos
bash install.sh
```

### 方式二：手动安装

```bash
# 1. 安装 Python 依赖 + Playwright 浏览器
bash scripts/setup.sh

# 2. 验证
python3 -c "import playwright, requests; print('deps ok')"
```

安装完成后，把 `booking-hotel-photos/` 目录放到 `~/.claude/skills/` 下即可在 Claude Code 中使用。

## 快速开始

```bash
# 一键抓取 + 下载
python3 src/download.py -q "大阪" --hotels 3 --headless

# 查看结果
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
