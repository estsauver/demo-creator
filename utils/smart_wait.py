"""
Smart waiting utilities for reliable browser automation.

Provides intelligent waiting that adapts to actual page conditions
rather than using fixed delays.
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


# Common loading indicators to wait for
DEFAULT_LOADING_SELECTORS = [
    ".loading",
    ".spinner",
    ".skeleton",
    "[aria-busy='true']",
    "[data-loading='true']",
    ".MuiCircularProgress-root",  # Material UI
    ".ant-spin",  # Ant Design
    ".chakra-spinner",  # Chakra UI
]


async def smart_wait_async(
    page,
    loading_selectors: Optional[List[str]] = None,
    animation_settle_ms: int = 300,
    network_idle_timeout: int = 5000,
) -> None:
    """
    Wait for page to be fully ready (async version).

    Instead of fixed delays, waits for actual conditions:
    1. Network requests to complete
    2. Loading indicators to disappear
    3. Brief pause for CSS animations

    Args:
        page: Playwright page object
        loading_selectors: Custom loading indicators to wait for
        animation_settle_ms: Time to wait for animations (ms)
        network_idle_timeout: Timeout for network idle (ms)
    """
    selectors = loading_selectors or DEFAULT_LOADING_SELECTORS

    # Wait for network to settle
    try:
        await page.wait_for_load_state("networkidle", timeout=network_idle_timeout)
    except Exception:
        logger.debug("Network idle timeout, continuing anyway")

    # Wait for loading indicators to disappear
    selector_string = ", ".join(selectors)
    try:
        await page.wait_for_function(
            f"""
            () => !document.querySelector('{selector_string}')
            """,
            timeout=5000,
        )
    except Exception:
        logger.debug("Loading indicator wait timeout, continuing anyway")

    # Brief pause for CSS animations to settle
    await page.wait_for_timeout(animation_settle_ms)


def smart_wait(
    page,
    loading_selectors: Optional[List[str]] = None,
    animation_settle_ms: int = 300,
    network_idle_timeout: int = 5000,
) -> None:
    """
    Wait for page to be fully ready (sync version).

    Instead of fixed delays, waits for actual conditions:
    1. Network requests to complete
    2. Loading indicators to disappear
    3. Brief pause for CSS animations

    Args:
        page: Playwright page object
        loading_selectors: Custom loading indicators to wait for
        animation_settle_ms: Time to wait for animations (ms)
        network_idle_timeout: Timeout for network idle (ms)
    """
    selectors = loading_selectors or DEFAULT_LOADING_SELECTORS

    # Wait for network to settle
    try:
        page.wait_for_load_state("networkidle", timeout=network_idle_timeout)
    except Exception:
        logger.debug("Network idle timeout, continuing anyway")

    # Wait for loading indicators to disappear
    selector_string = ", ".join(selectors)
    try:
        page.wait_for_function(
            f"""
            () => !document.querySelector('{selector_string}')
            """,
            timeout=5000,
        )
    except Exception:
        logger.debug("Loading indicator wait timeout, continuing anyway")

    # Brief pause for CSS animations to settle
    page.wait_for_timeout(animation_settle_ms)


def wait_for_element_stable(
    page,
    selector: str,
    stability_ms: int = 500,
    timeout: int = 10000,
) -> bool:
    """
    Wait for an element to be stable (not moving/resizing).

    Useful for elements that animate into position.

    Args:
        page: Playwright page object
        selector: Element selector
        stability_ms: Time element must be stable (ms)
        timeout: Total timeout (ms)

    Returns:
        True if element became stable, False if timeout
    """
    try:
        page.wait_for_function(
            f"""
            (selector, stabilityMs) => {{
                const el = document.querySelector(selector);
                if (!el) return false;

                return new Promise((resolve) => {{
                    let lastRect = el.getBoundingClientRect();
                    let stableTime = 0;
                    const checkInterval = 50;

                    const check = () => {{
                        const rect = el.getBoundingClientRect();
                        const same = (
                            rect.x === lastRect.x &&
                            rect.y === lastRect.y &&
                            rect.width === lastRect.width &&
                            rect.height === lastRect.height
                        );

                        if (same) {{
                            stableTime += checkInterval;
                            if (stableTime >= stabilityMs) {{
                                resolve(true);
                                return;
                            }}
                        }} else {{
                            stableTime = 0;
                            lastRect = rect;
                        }}

                        setTimeout(check, checkInterval);
                    }};

                    check();
                }});
            }}
            """,
            [selector, stability_ms],
            timeout=timeout,
        )
        return True
    except Exception:
        logger.debug(f"Element {selector} did not stabilize within timeout")
        return False


def wait_for_no_animation(
    page,
    timeout: int = 5000,
) -> bool:
    """
    Wait for all CSS animations to complete.

    Args:
        page: Playwright page object
        timeout: Total timeout (ms)

    Returns:
        True if animations completed, False if timeout
    """
    try:
        page.wait_for_function(
            """
            () => {
                const animations = document.getAnimations();
                return animations.every(a => a.playState !== 'running');
            }
            """,
            timeout=timeout,
        )
        return True
    except Exception:
        logger.debug("Animation wait timeout")
        return False


def wait_for_idle(
    page,
    idle_time_ms: int = 500,
    timeout: int = 10000,
) -> bool:
    """
    Wait for page to be truly idle (no DOM mutations, network, etc.).

    Args:
        page: Playwright page object
        idle_time_ms: Time with no activity to consider idle (ms)
        timeout: Total timeout (ms)

    Returns:
        True if page became idle, False if timeout
    """
    try:
        page.wait_for_function(
            f"""
            (idleTime) => {{
                return new Promise((resolve) => {{
                    let lastActivity = Date.now();
                    let resolved = false;

                    // Watch for DOM mutations
                    const observer = new MutationObserver(() => {{
                        lastActivity = Date.now();
                    }});
                    observer.observe(document.body, {{
                        childList: true,
                        subtree: true,
                        attributes: true,
                    }});

                    // Check periodically
                    const check = () => {{
                        if (resolved) return;

                        if (Date.now() - lastActivity >= idleTime) {{
                            resolved = true;
                            observer.disconnect();
                            resolve(true);
                        }} else {{
                            setTimeout(check, 100);
                        }}
                    }};

                    setTimeout(check, 100);
                }});
            }}
            """,
            idle_time_ms,
            timeout=timeout,
        )
        return True
    except Exception:
        logger.debug("Idle wait timeout")
        return False
