from __future__ import annotations

import base64
import ipaddress
import os
import socket
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class WebsiteScanError(Exception):
    pass


def _url_is_public(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost" or host.endswith(".localhost"):
            return False
        infos = socket.getaddrinfo(
            host,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
        return bool(infos) and all(ipaddress.ip_address(item[4][0]).is_global for item in infos)
    except Exception:
        return False


def _screenshot_base64(page, quality: int, timeout_ms: int) -> str:
    raw = page.screenshot(
        full_page=True,
        type="jpeg",
        quality=quality,
        timeout=timeout_ms,
        animations="disabled",
    )
    return base64.b64encode(raw).decode("ascii")


def scan_website(url: str) -> dict:
    if not _url_is_public(url):
        raise WebsiteScanError("The website resolved to a private or reserved destination. Scan cancelled.")

    timeout_ms = int(os.getenv("SCAN_TIMEOUT_MS", "30000"))
    result = {
        "requested_url": url,
        "final_url": url,
        "title": "",
        "meta_description": "",
        "headings": [],
        "buttons": [],
        "links": [],
        "images": {"total": 0, "missing_alt": 0},
        "signals": {},
        "screenshots": {},
        "warnings": [],
    }

    def route_guard(route):
        target = route.request.url
        parsed = urlparse(target)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            route.abort()
            return
        if not _url_is_public(target):
            route.abort()
            return
        route.continue_()

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                desktop_context = browser.new_context(
                    viewport={"width": 1365, "height": 900},
                    device_scale_factor=1,
                    ignore_https_errors=False,
                )
                desktop_page = desktop_context.new_page()
                desktop_page.route("**/*", route_guard)
                try:
                    desktop_page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                except PlaywrightTimeoutError:
                    raise WebsiteScanError("The website took too long to load. Try another public website.")
                except Exception as exc:
                    raise WebsiteScanError(
                        f"Could not load the website ({type(exc).__name__}). It may block automated browsers or have a TLS/network issue."
                    )

                try:
                    desktop_page.wait_for_load_state("networkidle", timeout=5000)
                except PlaywrightTimeoutError:
                    result["warnings"].append("Some dynamic content may still be loading.")

                result["final_url"] = desktop_page.url
                result["title"] = (desktop_page.title() or "")[:300]
                result["meta_description"] = (
                    desktop_page.locator('meta[name="description"]').get_attribute("content") or ""
                )[:600]
                result["headings"] = desktop_page.locator("h1, h2, h3").evaluate_all(
                    """els => els.slice(0, 30).map(e => ({
                        tag: e.tagName.toLowerCase(),
                        text: (e.innerText || '').trim().slice(0, 180)
                    })).filter(x => x.text)"""
                )
                result["buttons"] = desktop_page.locator(
                    "button, a[role='button'], input[type='submit']"
                ).evaluate_all(
                    """els => els.slice(0, 50).map(e => ({
                        tag: e.tagName.toLowerCase(),
                        text: ((e.innerText || e.value || e.getAttribute('aria-label') || '').trim()).slice(0, 100)
                    }))"""
                )
                result["links"] = desktop_page.locator("a[href]").evaluate_all(
                    """els => els.slice(0, 60).map(e => ({
                        text: (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 100),
                        href: e.href
                    }))"""
                )
                result["images"] = desktop_page.locator("img").evaluate_all(
                    """els => ({
                        total: els.length,
                        missing_alt: els.filter(e => !(e.getAttribute('alt') || '').trim()).length
                    })"""
                )
                result["signals"] = desktop_page.evaluate(
                    """() => {
                      const raw = document.body?.innerText || '';
                      const text = raw.slice(0, 50000).toLowerCase();
                      const actions = [...document.querySelectorAll('a,button,input[type=submit]')].map(e =>
                        ((e.innerText || e.value || e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('href') || '')).toLowerCase()
                      );
                      return {
                        viewport_meta: !!document.querySelector('meta[name="viewport"]'),
                        has_contact_terms: /contact|call us|phone|email|address/.test(text),
                        has_trust_terms: /reviews|testimonials|trusted|rated|customers|case studies/.test(text),
                        has_price_terms: /price|pricing|₹|\\$|£|€|cost/.test(text),
                        has_primary_action: actions.some(s => /book now|order now|get started|shop now|buy now|contact us|request a quote|sign up|subscribe|call now/.test(s)),
                        body_word_count: raw.trim().split(/\\s+/).filter(Boolean).length,
                        page_width: document.documentElement.scrollWidth,
                        viewport_width: window.innerWidth,
                        horizontal_overflow: document.documentElement.scrollWidth > window.innerWidth + 8
                      };
                    }"""
                )
                result["screenshots"]["desktop_jpeg_base64"] = _screenshot_base64(
                    desktop_page, quality=65, timeout_ms=timeout_ms
                )

                # Mobile is a separate browser context; BrowserContext.new_page() takes no viewport arguments.
                mobile_context = browser.new_context(
                    viewport={"width": 390, "height": 844},
                    device_scale_factor=1,
                    is_mobile=True,
                    has_touch=True,
                    ignore_https_errors=False,
                )
                try:
                    mobile_page = mobile_context.new_page()
                    mobile_page.route("**/*", route_guard)
                    mobile_page.goto(result["final_url"], wait_until="domcontentloaded", timeout=timeout_ms)
                    mobile_page.wait_for_timeout(350)
                    result["signals"]["mobile_horizontal_overflow"] = mobile_page.evaluate(
                        "document.documentElement.scrollWidth > window.innerWidth + 8"
                    )
                    result["screenshots"]["mobile_jpeg_base64"] = _screenshot_base64(
                        mobile_page, quality=55, timeout_ms=timeout_ms
                    )
                except Exception as exc:
                    result["warnings"].append(f"Mobile screenshot could not be captured ({type(exc).__name__}).")
                finally:
                    mobile_context.close()
                desktop_context.close()
            finally:
                browser.close()
    except WebsiteScanError:
        raise
    except Exception as exc:
        raise WebsiteScanError(
            f"Playwright scan failed ({type(exc).__name__}): {str(exc)[:250] or 'No additional details'}. "
            "Try `python -m playwright install chromium`."
        )

    return result
