#!/usr/bin/env python3
"""
第一步：用 Playwright 获取酒店列表和图片 URL
输出: hotel_urls.json (包含每家酒店的所有图片URL)

用法:
  python fetch_urls.py --query "拉斯维加斯" --pages 3
  python fetch_urls.py --query "东京" --pages 5 --output tokyo_urls.json
"""

import argparse
import json
import logging
import random
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Set

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("fetch_urls")

BASE_URL = "https://www.booking.com"
SEARCH_URL = f"{BASE_URL}/searchresults.html"

# 图片尺寸映射
IMAGE_SIZES = {
    "thumb": "max300",
    "medium": "max500",
    "large": "max1024x768",
    "xlarge": "max2048x1536",
}

# 仅保留 Booking 酒店图库 CDN 上的真实照片
HOTEL_PHOTO_PATH_RE = re.compile(r"/xdata/images/hotel/", re.I)
HOTEL_PHOTO_EXT_RE = re.compile(r"\.(jpe?g|webp)(?:\?|$)", re.I)


@dataclass
class PhotoInfo:
    url: str
    alt: str = ""
    category: str = ""


@dataclass
class HotelInfo:
    name: str
    url: str
    hotel_id: str = ""
    rating: str = ""
    review_count: str = ""
    price: str = ""
    address: str = ""
    photos: List[dict] = field(default_factory=list)


@dataclass
class GalleryExpectation:
    """Booking 图库文案语义：首屏预览若干张 +「更多 N 张」= 另有 N 张（与预览去重后合计约 preview+N）"""
    preview_count: int = 0
    more_count: int = 0

    @property
    def total_expected(self) -> int:
        if self.more_count <= 0:
            return max(self.preview_count, 0)
        return self.preview_count + self.more_count


def normalize_photo_url(url: str) -> str:
    """修复从 script JSON 抠出的 URL（\\u0026 → & 等），否则 CDN 返回 401"""
    if not url:
        return url
    return (
        url.replace("\\u0026", "&")
        .replace("\\u003d", "=")
        .replace("\\/", "/")
    )


def is_valid_hotel_photo_url(url: str) -> bool:
    """过滤头像、国旗、SVG/ICO/GIF 占位图等非酒店照片资源"""
    if not url or not url.startswith("http"):
        return False
    lower = url.lower()
    if not HOTEL_PHOTO_PATH_RE.search(lower):
        return False
    if not HOTEL_PHOTO_EXT_RE.search(lower):
        return False
    blocked = (
        "/avatars/",
        "/static/img/",
        "/design-assets/",
        "images-flags",
        "/illustrations-",
        "/xphoto/",  # 住客上传等非官方图库
        ".svg",
        ".ico",
        ".gif",
        ".png",  # 酒店照片一般为 jpg/webp
    )
    return not any(b in lower for b in blocked)


def upgrade_image_url(url: str, size: str = "large") -> str:
    """将图片 URL 升级为更大尺寸"""
    if not url:
        return url
    target_size = IMAGE_SIZES.get(size, "max1024x768")
    return re.sub(r"/hotel/\w+/", f"/hotel/{target_size}/", url)


def deduplicate_photos(photos: List[PhotoInfo]) -> List[PhotoInfo]:
    """根据图片 ID 去重（仅处理合法酒店照片 URL）"""
    seen: Set[str] = set()
    unique: List[PhotoInfo] = []
    for p in photos:
        if not is_valid_hotel_photo_url(p.url):
            continue
        m = re.search(r"/(\d+)\.(?:jpg|webp)", p.url, re.I)
        if m:
            img_id = m.group(1)
            if img_id not in seen:
                seen.add(img_id)
                unique.append(p)
    return unique


def random_delay(min_s: float = 0.6, max_s: float = 1.4):
    """随机延迟"""
    time.sleep(random.uniform(min_s, max_s))


def build_search_url(query: str, page: int = 0, **kwargs) -> str:
    """构建搜索 URL"""
    params = [f"ss={query}"]
    if page > 0:
        params.append(f"offset={page * 25}")
    for k, v in kwargs.items():
        if v is not None and v != "":
            params.append(f"{k}={v}")
    return f"{SEARCH_URL}?{'&'.join(params)}"


def create_stealth_context(browser: Browser) -> BrowserContext:
    """创建带反检测的浏览器上下文"""
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        locale="zh-CN",
        timezone_id="Asia/Shanghai",
        extra_http_headers={
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    # 注入反检测脚本
    context.add_init_script("""
    // 覆盖 navigator.webdriver
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });

    // 覆盖 chrome 对象
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };

    // 覆盖 permissions
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
    );

    // 覆盖 plugins
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5]
    });

    // 覆盖 languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en']
    });
    """)

    return context


def fetch_search_page(page: Page, url: str, max_retries: int = 3) -> bool:
    """加载搜索页，带重试"""
    for attempt in range(max_retries):
        try:
            logger.info("正在加载: %s", url)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # 等待酒店卡片出现
            page.wait_for_selector('[data-testid="property-card"]', timeout=20000)
            # 额外短等待，平衡稳定性与速度
            time.sleep(0.8)
            return True
        except Exception as e:
            logger.warning("加载失败 (尝试 %d/%d): %s", attempt + 1, max_retries, e)
            time.sleep(3)
    return False


def parse_hotels_from_page(page: Page) -> List[HotelInfo]:
    """从当前页面解析酒店列表"""
    hotels = page.evaluate("""
    () => {
        const cards = document.querySelectorAll('[data-testid="property-card"]');
        const results = [];
        cards.forEach(card => {
            const titleEl = card.querySelector('[data-testid="title"]');
            const linkEl = card.querySelector('[data-testid="title-link"]') ||
                           card.querySelector('a[href*="/hotel/"]');
            const ratingEl = card.querySelector('[data-testid="review-score"]');
            const priceEl = card.querySelector('[data-testid="price-and-discounted-price"]');
            const addrEl = card.querySelector('[data-testid="address-link"]');

            if (!titleEl || !linkEl) return;

            const href = linkEl.getAttribute('href') || '';
            const hotelIdMatch = href.match(/\\/hotel\\/[^/]+\\/([^/.]+)\\.?/);
            const hotelId = hotelIdMatch ? hotelIdMatch[1] : '';

            results.push({
                name: titleEl.textContent.trim(),
                url: href.startsWith('http') ? href : 'https://www.booking.com' + href,
                hotel_id: hotelId,
                rating: ratingEl ? ratingEl.textContent.trim() : '',
                price: priceEl ? priceEl.textContent.trim() : '',
                address: addrEl ? addrEl.textContent.trim() : '',
            });
        });
        return results;
    }
    """)
    return [HotelInfo(**h) for h in (hotels or [])]


def parse_gallery_expectation(page: Page) -> GalleryExpectation:
    """
    解析图库预期（仅看画廊区域，避免整页 textContent 误匹配）：
    - preview_count: .hp-gallery-grid 内首屏酒店图（不含「更多」遮罩里的重复计数）
    - more_count: 「更多 N 张照片」里的 N（表示在预览之外还有 N 张，不是全站总数）
    """
    data = page.evaluate("""
    () => {
        let preview = 0;
        const grid = document.querySelector('.hp-gallery-grid');
        if (grid) {
            grid.querySelectorAll('img').forEach(img => {
                if (img.closest('[data-testid="host-image"]')) return;
                const src = img.getAttribute('src') || img.getAttribute('data-src') || '';
                if (!/\\/xdata\\/images\\/hotel\\/.*\\.(jpe?g|webp)/i.test(src)) return;
                preview += 1;
            });
        }
        let more = 0;
        const overlay = document.querySelector('[data-testid="GalleryUnifiedDesktop-wrapper"]');
        if (overlay) {
            const m = (overlay.textContent || '').match(/更多\\s*(\\d+)\\s*张照片/);
            if (m) more = parseInt(m[1], 10);
        }
        if (!more && grid) {
            const m2 = (grid.innerText || '').match(/更多\\s*(\\d+)\\s*张照片/);
            if (m2) more = parseInt(m2[1], 10);
        }
        return { preview, more };
    }
    """)
    return GalleryExpectation(
        preview_count=int(data.get("preview", 0) or 0),
        more_count=int(data.get("more", 0) or 0),
    )


def open_full_photo_gallery(page: Page) -> bool:
    """点击「更多 N 张照片」打开完整图库（懒加载前需先点开）"""
    try:
        page.wait_for_selector(".hp-gallery-grid", timeout=15000)
    except Exception:
        return False

    targets = [
        page.locator('[data-testid="GalleryUnifiedDesktop-wrapper"]').first,
        page.locator(".hp-gallery-grid").get_by_text(re.compile(r"更多\s*\d+\s*张照片")).first,
        page.get_by_text(re.compile(r"更多\s*\d+\s*张照片")).first,
    ]
    for loc in targets:
        try:
            if loc.count() == 0:
                continue
            loc.click(timeout=8000)
            try:
                page.wait_for_selector(
                    '[role="dialog"], [data-testid*="Gallery" i]',
                    timeout=12000,
                )
            except Exception:
                pass
            page.wait_for_timeout(2000)
            return True
        except Exception:
            continue
    return False


def count_hotel_photos_in_dom(page: Page, scope: str = "modal") -> int:
    """统计图库范围内的酒店照片（默认仅弹层，避免把全页 script/预览重复算进去）"""
    items = collect_hotel_photo_urls_from_page(page, scope)
    return len({p["url"].split("?")[0] for p in items if p.get("url")})


def scroll_gallery_for_lazy_load(
    page: Page,
    max_rounds: int = 50,
    stable_rounds: int = 4,
    step_pause_ms: int = 300,
) -> Set[str]:
    """
    图库为懒加载 / 虚拟列表：滚动时 DOM 里可能始终只有少量 img，
    必须在每一屏把 URL 累加进集合，不能等滚完再数节点。
    """
    exp = parse_gallery_expectation(page)
    min_target = exp.total_expected if exp.total_expected > 0 else 40
    if exp.more_count > 0 or exp.preview_count > 0:
        logger.info(
            "  文案: 预览 %d + 更多 %d → 预期唯一约 %d 张（URL 去重），边滚边收集…",
            exp.preview_count,
            exp.more_count,
            min_target,
        )

    accumulated: dict[str, str] = {}  # base_url -> 带 query 的完整 URL
    prev_total = 0
    stable = 0

    def _merge_batch():
        # 只从图库弹层收集，不把全页 <script> 里多尺寸重复 URL 算进「累计」
        for item in collect_hotel_photo_urls_from_page(page, "modal"):
            url = item.get("url", "")
            if not is_valid_hotel_photo_url(url):
                continue
            url = normalize_photo_url(url)
            base = url.split("?")[0]
            if base not in accumulated:
                accumulated[base] = url

    _merge_batch()

    for round_i in range(max_rounds):
        page.evaluate("""
        () => {
            const scrollables = [];
            const sel = [
                '[role="dialog"]',
                '[data-testid*="gallery" i]',
                '[data-testid*="Gallery" i]',
                '[class*="lightbox" i]',
                '[class*="Gallery" i]',
            ].join(', ');
            document.querySelectorAll(sel).forEach(el => {
                if (el.scrollHeight > el.clientHeight + 20) scrollables.push(el);
            });
            scrollables.sort(
                (a, b) => (b.scrollHeight - b.clientHeight) - (a.scrollHeight - a.clientHeight)
            );
            const target = scrollables[0];
            if (target) {
                const step = Math.max(target.clientHeight * 0.75, 260);
                target.scrollTop = Math.min(target.scrollTop + step, target.scrollHeight);
            } else {
                window.scrollBy(0, window.innerHeight * 0.75);
            }
        }
        """)
        page.wait_for_timeout(step_pause_ms)
        _merge_batch()

        total = len(accumulated)
        if min_target > 0 and total >= min_target * 0.9:
            logger.info(
                "  懒加载达标: 去重后 %d / 预期约 %d (预览%d+更多%d, 滚 %d 轮)",
                total, min_target, exp.preview_count, exp.more_count, round_i + 1,
            )
            return set(accumulated.values())

        if total == prev_total:
            stable += 1
            if stable >= stable_rounds:
                if min_target > 0 and total < min_target * 0.7:
                    stable = 0
                    page.evaluate("""
                    () => {
                        document.querySelectorAll('[role="dialog"], [data-testid*="Gallery" i]')
                            .forEach(el => { el.scrollTop = el.scrollHeight; });
                    }
                    """)
                    page.wait_for_timeout(step_pause_ms * 2)
                    _merge_batch()
                    continue
                logger.info("  懒加载收集稳定: %d 张 (滚 %d 轮)", total, round_i + 1)
                return set(accumulated.values())
        else:
            stable = 0
            prev_total = total

    logger.info("  懒加载达滚动上限: 累计 %d 张 (滚 %d 轮)", len(accumulated), max_rounds)
    return set(accumulated.values())


def collect_hotel_photo_urls_from_page(page: Page, scope: str = "all") -> List[dict]:
    """
    按范围收集酒店照片 URL。
    - preview: 仅首屏 .hp-gallery-grid
    - modal: 仅图库弹层（懒加载滚动应用此范围）
    - all: preview + modal（不含 script，避免预览+JSON 重复膨胀）
  - scripts: 仅作兜底，易含同图多尺寸重复
    """
    raw = page.evaluate(
        """
    (scope) => {
        const items = [];
        const seen = new Set();

        function normalizeUrl(url) {
            return url
                .replace(/\\\\u0026/gi, '&')
                .replace(/\\\\u003d/gi, '=')
                .replace(/\\\\\\//g, '/');
        }

        function add(url, alt, category) {
            url = normalizeUrl(url || '');
            if (!url || !url.includes('/xdata/images/hotel/')) return;
            if (!/\\.(jpe?g|webp)(\\?|$)/i.test(url)) return;
            const key = url.split('?')[0];
            if (seen.has(key)) return;
            seen.add(key);
            items.push({ url, alt: alt || '', category: category || 'gallery' });
        }

        function collectImgs(root, category) {
            if (!root) return;
            root.querySelectorAll('img').forEach(img => {
                if (img.closest('[data-testid="host-image"]')) return;
                const alt = img.getAttribute('alt') || '';
                for (const attr of ['src', 'data-src', 'data-lazy', 'data-original']) {
                    add(img.getAttribute(attr) || '', alt, category);
                }
                const srcset = img.getAttribute('srcset') || '';
                srcset.split(',').forEach(part => {
                    add(part.trim().split(/\\s+/)[0], alt, category);
                });
            });
        }

        const usePreview = scope === 'preview' || scope === 'all';
        const useModal = scope === 'modal' || scope === 'all';
        const useScripts = scope === 'scripts';

        if (usePreview) {
            collectImgs(document.querySelector('.hp-gallery-grid'), 'preview');
        }
        if (useModal) {
            document.querySelectorAll(
                '[role="dialog"], [data-testid*="Gallery" i], [class*="lightbox" i]'
            ).forEach(root => collectImgs(root, 'modal'));
        }
        if (useScripts) {
            const hotelRe = /https?:\\/\\/[^"'\\s]+\\/xdata\\/images\\/hotel\\/[^"'\\s]+?\\.(?:jpe?g|webp)[^"'\\s]*/gi;
            document.querySelectorAll('script').forEach(s => {
                const text = s.textContent || '';
                let m;
                while ((m = hotelRe.exec(text)) !== null) {
                    add(m[0], '', 'embedded');
                }
            });
        }

        return items;
    }
    """,
        scope,
    )
    return raw or []


def fetch_hotel_photos(page: Page, hotel: HotelInfo, image_size: str = "large") -> List[PhotoInfo]:
    """访问酒店详情页，打开完整图库并获取全部照片 URL"""
    try:
        page.goto(hotel.url, wait_until="domcontentloaded", timeout=30000)

        try:
            page.wait_for_selector(".hp-gallery-grid", timeout=15000)
        except Exception:
            logger.warning("未找到画廊区域: %s", hotel.name)
            return []

        exp = parse_gallery_expectation(page)
        before = len(collect_hotel_photo_urls_from_page(page, "preview"))

        scrolled_urls: Set[str] = set()
        if open_full_photo_gallery(page):
            scrolled_urls = scroll_gallery_for_lazy_load(page)
            logger.info("  已打开完整图库并完成懒加载滚动收集")
        else:
            logger.warning("  未能点击「更多照片」，仅抓取首屏: %s", hotel.name)

        # 合并：滚动累计（modal）+ 首屏预览（preview），按图片 ID 去重（预览 ⊆ 全库，不会重复计数）
        raw_photos = collect_hotel_photo_urls_from_page(page, "all")
        seen_keys: Set[str] = set()
        photos: List[PhotoInfo] = []

        def _add_photo(url: str, alt: str = "", category: str = "gallery"):
            url = normalize_photo_url(url)
            if not is_valid_hotel_photo_url(url):
                return
            key = url.split("?")[0]
            if key in seen_keys:
                return
            seen_keys.add(key)
            photos.append(PhotoInfo(url=url, alt=alt, category=category))

        for url in scrolled_urls:
            _add_photo(url, category="modal")

        for p in raw_photos:
            _add_photo(p.get("url", ""), p.get("alt", ""), p.get("category", "gallery"))

        # 仍明显不足时，才用 script 兜底（不参与滚动阶段的「累计」判断）
        if exp.total_expected > 0 and len(photos) < exp.total_expected * 0.85:
            for p in collect_hotel_photo_urls_from_page(page, "scripts"):
                _add_photo(p.get("url", ""), p.get("alt", ""), "embedded")

        after = len(photos)
        if exp.total_expected > 0:
            logger.info(
                "  结果: 去重后 %d 张 | 文案预期约 %d (预览%d+更多%d) | 滚动收集 %d",
                after,
                exp.total_expected,
                exp.preview_count,
                exp.more_count,
                len(scrolled_urls),
            )
        elif after > before:
            logger.info("  图库展开: %d → %d 张", before, after)

        return photos

    except Exception as e:
        logger.error("获取酒店照片失败 %s: %s", hotel.name, e)
        return []


def run(query: str, pages: int = 1, output: str = "hotel_urls.json",
        image_size: str = "large", headless: bool = True,
        checkin: str = "", checkout: str = "", max_hotels: int = 0,
        min_delay: float = 0.6, max_delay: float = 1.4):
    """主流程"""

    all_hotels: List[HotelInfo] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ]
        )
        context = create_stealth_context(browser)

        page = context.new_page()

        try:
            # 1. 抓取搜索页
            for page_num in range(pages):
                url = build_search_url(
                    query, page_num,
                    checkin=checkin, checkout=checkout
                )

                if not fetch_search_page(page, url):
                    logger.error("无法加载第 %d 页", page_num + 1)
                    continue

                hotels = parse_hotels_from_page(page)
                logger.info("第 %d 页找到 %d 家酒店", page_num + 1, len(hotels))
                all_hotels.extend(hotels)

                if page_num < pages - 1:
                    random_delay(min_delay, max_delay)

            # 去重
            seen_ids: Set[str] = set()
            unique_hotels: List[HotelInfo] = []
            for h in all_hotels:
                key = h.hotel_id or h.url
                if key not in seen_ids:
                    seen_ids.add(key)
                    unique_hotels.append(h)
            all_hotels = unique_hotels

            # 在进入详情页抓图前限制酒店数量，避免测试时耗时过长
            if max_hotels and max_hotels > 0:
                all_hotels = all_hotels[:max_hotels]
                logger.info("已限制酒店数为前 %d 家", len(all_hotels))

            logger.info("共 %d 家酒店（去重后），开始获取照片...", len(all_hotels))

            # 2. 逐个获取酒店照片
            for i, hotel in enumerate(all_hotels, 1):
                logger.info("[%d/%d] %s", i, len(all_hotels), hotel.name)

                photos = fetch_hotel_photos(page, hotel, image_size)
                photos = deduplicate_photos(photos)

                # 升级图片 URL
                for p_info in photos:
                    p_info.url = upgrade_image_url(p_info.url, image_size)

                hotel.photos = [asdict(p) for p in photos]
                logger.info("  → %d 张照片", len(photos))

                if i < len(all_hotels):
                    random_delay(min_delay, max_delay)

        finally:
            context.close()
            browser.close()

    # 3. 保存结果
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "query": query,
        "total_hotels": len(all_hotels),
        "total_photos": sum(len(h.photos) for h in all_hotels),
        "hotels": [asdict(h) for h in all_hotels],
    }

    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("=" * 60)
    logger.info("完成！")
    logger.info("酒店数: %d", len(all_hotels))
    logger.info("照片总数: %d", data["total_photos"])
    logger.info("保存至: %s", output_path.resolve())
    logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="获取 Booking.com 酒店图片 URL")
    parser.add_argument("--query", "-q", required=True, help="搜索关键词")
    parser.add_argument("--pages", "-p", type=int, default=1, help="搜索页数")
    parser.add_argument("--output", "-o", default="hotel_urls.json", help="输出 JSON 文件")
    parser.add_argument("--image-size", choices=["thumb", "medium", "large", "xlarge"], default="large")
    parser.add_argument("--headless", action="store_true", help="无头模式（默认有界面）")
    parser.add_argument("--checkin", default="", help="入住日期 YYYY-MM-DD")
    parser.add_argument("--checkout", default="", help="退房日期 YYYY-MM-DD")
    parser.add_argument("--max-hotels", type=int, default=0, help="最多处理酒店数（0 表示不限制）")
    parser.add_argument("--min-delay", type=float, default=0.6, help="请求间最小随机延迟秒数")
    parser.add_argument("--max-delay", type=float, default=1.4, help="请求间最大随机延迟秒数")

    args = parser.parse_args()

    run(
        query=args.query,
        pages=args.pages,
        output=args.output,
        image_size=args.image_size,
        headless=args.headless,
        checkin=args.checkin,
        checkout=args.checkout,
        max_hotels=args.max_hotels,
        min_delay=args.min_delay,
        max_delay=args.max_delay,
    )


if __name__ == "__main__":
    main()
