# Booking 照片抓取 — 技术参考

## 架构

1. `fetch_urls.py` — Playwright 搜索 → 点「更多 N 张照片」→ 图库边滚边收集 URL → JSON
2. `download_photos.py` — 并发下载，跳过已存在文件
3. `download.py` — 一键封装
4. `config.py` — `config.json` / `BOOKING_OUTPUT_DIR`

## 图库语义

- 预览约 8 张 + 文案「更多 N 张」→ 预期唯一约 preview+N（URL 去重）
- 懒加载/虚拟列表：边滚边累加 URL

## URL

仅 `/xdata/images/hotel/*.jpg|webp`；script 来源须 `normalize_photo_url`（`\u0026` → `&`），否则 401。
