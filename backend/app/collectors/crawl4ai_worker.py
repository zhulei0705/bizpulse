"""仅由受信任适配器启动。所有浏览器请求由 DNS 固定 HTTP 桥接；不可直连网络。"""
from __future__ import annotations
import asyncio
import json
import socket
import sys
import os
from pathlib import Path
from urllib.parse import urlsplit

from app.collectors.crawl_policy import SafeFetch, CrawlStopped, check_url


async def run(payload: dict) -> dict:
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
    client = SafeFetch(set(payload["domains"]), interval=payload["interval"], allowed_paths=payload.get("allowed_paths"))
    client.pins = {k: frozenset(v) for k,v in payload["pins"].items()}
    client.bytes = payload["bytes_used"]
    client.requests = payload["requests_used"]
    stopped = []
    blocked = []
    # 保留一个绑定但不监听的端口：未被 route 截获的网络只能失败，不能绕过桥接。
    with socket.socket() as sink:
        sink.bind(("127.0.0.1", 0))
        proxy = f"http://127.0.0.1:{sink.getsockname()[1]}"
        config = BrowserConfig(headless=True, verbose=False, accept_downloads=False,
             user_agent="BizPulseBot/0.1", proxy_config={"server": proxy, "bypass": "<-loopback>"},
             extra_args=["--disable-quic", "--disable-background-networking", "--disable-extensions",
                         "--proxy-bypass-list=<-loopback>"])
        async def hook(page, context, **kwargs):
            async def route_request(route):
                request = route.request
                p = urlsplit(request.url)
                if p.hostname not in client.domains:
                    # 外部广告/字体也不外连；私网/非 HTTP 企图属于严重停止条件。
                    import ipaddress
                    try:
                        private = p.hostname and not ipaddress.ip_address(p.hostname).is_global
                    except ValueError:
                        private = p.hostname in {"localhost"} or (p.hostname or "").endswith((".local", ".internal"))
                    if private or p.scheme not in {"http", "https", "data", "about"}:
                        stopped.append("UNSAFE_BROWSER_TARGET")
                    blocked.append("EXTERNAL_RESOURCE_BLOCKED")
                    await route.abort()
                    return
                if request.method != "GET" or request.resource_type in {"image", "media", "font"}:
                    await route.abort()
                    return
                try:
                    check_url(request.url, client.domains)
                    if request.url == payload["url"] and request.is_navigation_request():
                        await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=payload["html"])
                    else:
                        response = await asyncio.to_thread(client.get, request.url)
                        await route.fulfill(status=response.status, content_type=response.content_type, body=response.body)
                except CrawlStopped as exc:
                    stopped.append(str(exc))
                    await route.abort()
            # context 级规则覆盖 iframe / popup；下载、WebSocket 与 service worker 均不放行。
            await context.route("**/*", route_request)
            if hasattr(context, "route_web_socket"):
                await context.route_web_socket("**/*", lambda ws: ws.close())
            await context.add_init_script("Object.defineProperty(navigator,'serviceWorker',{value:undefined});")
            return page
        async with AsyncWebCrawler(config=config, base_directory=os.environ["CRAWL4_AI_BASE_DIRECTORY"]) as crawler:
            crawler.crawler_strategy.set_hook("on_page_context_created", hook)
            result = await crawler.arun(payload["url"], config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS, page_timeout=25000, delay_before_return_html=payload["wait_ms"]/1000,
                check_robots_txt=False, verbose=False, word_count_threshold=1,
                process_iframes=False, scan_full_page=False))
            # SDK 的内置 robots 不再另行联网；所有请求已在 SafeFetch 中逐跳强制校验 robots。
            if stopped:
                return {"stop": stopped[0]}
            if result.redirected_url and result.redirected_url != payload["url"]:
                return {"stop": "UNEXPECTED_BROWSER_NAVIGATION"}
            if not result.success:
                if "anti-bot" in (result.error_message or "").lower():
                    return {"stop": "ACCESS_BARRIER_STOP"}
                return {"stop": "SDK_RENDER_FAILED"}
            return {"html": result.html, "blocked_resources": blocked,
                    "bytes": client.bytes-payload["bytes_used"], "requests": client.requests-payload["requests_used"]}


if __name__ == "__main__":
    root = Path(sys.argv[1])
    payload = json.loads((root / "input.json").read_text(encoding="utf-8"))
    try:
        output = asyncio.run(run(payload))
    except Exception as exc:
        import traceback
        traceback.print_exc()
        output = {"stop": "SDK_RENDER_FAILED", "error_type": type(exc).__name__}
    (root / "output.json").write_text(json.dumps(output), encoding="utf-8")
