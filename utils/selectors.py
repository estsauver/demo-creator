"""
Selector discovery utilities for demo-creator.

Crawls web applications to discover robust selectors for interactive elements.
Prioritizes test-ids, aria-labels, and text-based selectors over CSS classes.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredElement:
    """Represents a discovered interactive element."""

    tag: str
    text: str
    selector: str
    selector_type: str  # test-id, aria-label, text, css
    priority: int  # Lower is better
    attributes: Dict[str, str] = field(default_factory=dict)
    bounding_box: Optional[Dict[str, float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tag": self.tag,
            "text": self.text,
            "selector": self.selector,
            "selector_type": self.selector_type,
            "priority": self.priority,
            "attributes": self.attributes,
            "bounding_box": self.bounding_box,
        }


class SelectorDiscovery:
    """
    Discovers robust selectors for interactive elements on web pages.

    Uses Playwright to crawl pages and identify the most resilient selectors.
    """

    # Selector priority (lower is more preferred)
    PRIORITY_TEST_ID = 1
    PRIORITY_ARIA_LABEL = 2
    PRIORITY_TEXT = 3
    PRIORITY_NAME = 4
    PRIORITY_PLACEHOLDER = 5
    PRIORITY_ROLE = 6
    PRIORITY_CSS_CLASS = 7

    def __init__(self, base_url: str):
        """
        Initialize selector discovery.

        Args:
            base_url: Base URL of the application
        """
        self.base_url = base_url
        self._page = None

    def discover_page(
        self,
        page,
        url: Optional[str] = None,
        include_hidden: bool = False,
    ) -> Dict[str, DiscoveredElement]:
        """
        Discover selectors for all interactive elements on a page.

        Args:
            page: Playwright page object
            url: Optional URL to navigate to (if not already there)
            include_hidden: Include hidden elements

        Returns:
            Dict mapping semantic names to DiscoveredElement objects
        """
        if url:
            page.goto(url)
            page.wait_for_load_state("networkidle")

        elements = {}

        # Discover buttons
        button_elements = self._discover_buttons(page, include_hidden)
        elements.update(button_elements)

        # Discover inputs
        input_elements = self._discover_inputs(page, include_hidden)
        elements.update(input_elements)

        # Discover links
        link_elements = self._discover_links(page, include_hidden)
        elements.update(link_elements)

        # Discover select dropdowns
        select_elements = self._discover_selects(page, include_hidden)
        elements.update(select_elements)

        logger.info(f"Discovered {len(elements)} interactive elements on {page.url}")
        return elements

    def _discover_buttons(
        self,
        page,
        include_hidden: bool = False,
    ) -> Dict[str, DiscoveredElement]:
        """Discover button elements."""
        elements = {}

        # Query all button-like elements
        selectors = [
            "button",
            "[role='button']",
            "input[type='submit']",
            "input[type='button']",
            "a.btn, a.button",
        ]

        for base_selector in selectors:
            locators = page.locator(base_selector).all()

            for locator in locators:
                try:
                    if not include_hidden and not locator.is_visible():
                        continue

                    element = self._analyze_element(locator, "button")
                    if element:
                        # Create semantic name
                        name = self._generate_name(element, "button")
                        elements[name] = element

                except Exception as e:
                    logger.debug(f"Error analyzing button element: {e}")

        return elements

    def _discover_inputs(
        self,
        page,
        include_hidden: bool = False,
    ) -> Dict[str, DiscoveredElement]:
        """Discover input elements."""
        elements = {}

        # Query input elements
        selectors = [
            "input[type='text']",
            "input[type='email']",
            "input[type='password']",
            "input[type='search']",
            "input[type='tel']",
            "input[type='url']",
            "input[type='number']",
            "input:not([type])",
            "textarea",
            "[contenteditable='true']",
        ]

        for base_selector in selectors:
            locators = page.locator(base_selector).all()

            for locator in locators:
                try:
                    if not include_hidden and not locator.is_visible():
                        continue

                    element = self._analyze_element(locator, "input")
                    if element:
                        name = self._generate_name(element, "input")
                        elements[name] = element

                except Exception as e:
                    logger.debug(f"Error analyzing input element: {e}")

        return elements

    def _discover_links(
        self,
        page,
        include_hidden: bool = False,
    ) -> Dict[str, DiscoveredElement]:
        """Discover link elements."""
        elements = {}

        locators = page.locator("a[href]").all()

        for locator in locators:
            try:
                if not include_hidden and not locator.is_visible():
                    continue

                element = self._analyze_element(locator, "link")
                if element:
                    name = self._generate_name(element, "link")
                    elements[name] = element

            except Exception as e:
                logger.debug(f"Error analyzing link element: {e}")

        return elements

    def _discover_selects(
        self,
        page,
        include_hidden: bool = False,
    ) -> Dict[str, DiscoveredElement]:
        """Discover select dropdown elements."""
        elements = {}

        locators = page.locator("select").all()

        for locator in locators:
            try:
                if not include_hidden and not locator.is_visible():
                    continue

                element = self._analyze_element(locator, "select")
                if element:
                    name = self._generate_name(element, "select")
                    elements[name] = element

            except Exception as e:
                logger.debug(f"Error analyzing select element: {e}")

        return elements

    def _analyze_element(
        self,
        locator,
        element_type: str,
    ) -> Optional[DiscoveredElement]:
        """
        Analyze an element and generate the best selector.

        Args:
            locator: Playwright locator
            element_type: Type of element (button, input, link, select)

        Returns:
            DiscoveredElement or None if no good selector found
        """
        try:
            # Get element attributes
            tag = locator.evaluate("el => el.tagName.toLowerCase()")
            text = locator.inner_text().strip()[:100]  # Limit text length
            bounding_box = locator.bounding_box()

            attributes = {}
            for attr in ["data-testid", "aria-label", "name", "placeholder", "id", "class", "type"]:
                value = locator.get_attribute(attr)
                if value:
                    attributes[attr] = value

            # Generate best selector
            selector, selector_type, priority = self._generate_selector(
                tag, text, attributes, element_type
            )

            if not selector:
                return None

            return DiscoveredElement(
                tag=tag,
                text=text,
                selector=selector,
                selector_type=selector_type,
                priority=priority,
                attributes=attributes,
                bounding_box=bounding_box,
            )

        except Exception as e:
            logger.debug(f"Error analyzing element: {e}")
            return None

    def _generate_selector(
        self,
        tag: str,
        text: str,
        attributes: Dict[str, str],
        element_type: str,
    ) -> Tuple[Optional[str], str, int]:
        """
        Generate the best selector for an element.

        Returns:
            Tuple of (selector, selector_type, priority)
        """
        # Priority 1: data-testid
        if "data-testid" in attributes:
            test_id = attributes["data-testid"]
            return f"[data-testid='{test_id}']", "test-id", self.PRIORITY_TEST_ID

        # Priority 2: aria-label
        if "aria-label" in attributes:
            aria = attributes["aria-label"]
            return f"[aria-label='{aria}']", "aria-label", self.PRIORITY_ARIA_LABEL

        # Priority 3: Text-based selector (for buttons and links)
        if text and element_type in ("button", "link"):
            # Clean and escape text
            clean_text = text.replace("'", "\\'")
            if len(clean_text) <= 50:  # Only use text if reasonably short
                return f"{tag}:has-text('{clean_text}')", "text", self.PRIORITY_TEXT

        # Priority 4: name attribute
        if "name" in attributes:
            name = attributes["name"]
            return f"{tag}[name='{name}']", "name", self.PRIORITY_NAME

        # Priority 5: placeholder (for inputs)
        if "placeholder" in attributes and element_type == "input":
            placeholder = attributes["placeholder"]
            return f"{tag}[placeholder='{placeholder}']", "placeholder", self.PRIORITY_PLACEHOLDER

        # Priority 6: Role-based with text
        if text and element_type == "button":
            clean_text = text.replace("'", "\\'")[:30]
            return f"[role='button']:has-text('{clean_text}')", "role", self.PRIORITY_ROLE

        # Priority 7: CSS class (last resort, fragile)
        if "class" in attributes:
            classes = attributes["class"].split()
            # Filter out utility classes
            meaningful_classes = [
                c for c in classes
                if not c.startswith(("p-", "m-", "text-", "bg-", "flex", "grid", "w-", "h-"))
                and len(c) > 2
            ]
            if meaningful_classes:
                selector = f"{tag}.{'.'.join(meaningful_classes[:2])}"
                return selector, "css", self.PRIORITY_CSS_CLASS

        return None, "", 999

    def _generate_name(self, element: DiscoveredElement, element_type: str) -> str:
        """Generate a semantic name for an element."""
        # Use text content if available
        if element.text:
            # Clean and format text
            name = element.text.lower().strip()
            name = name.replace(" ", "_").replace("-", "_")
            name = "".join(c for c in name if c.isalnum() or c == "_")
            name = name[:30]  # Limit length
            return f"{element_type}_{name}"

        # Use attribute-based name
        if "aria-label" in element.attributes:
            label = element.attributes["aria-label"].lower()[:30]
            label = label.replace(" ", "_")
            return f"{element_type}_{label}"

        if "name" in element.attributes:
            return f"{element_type}_{element.attributes['name']}"

        if "placeholder" in element.attributes:
            placeholder = element.attributes["placeholder"].lower()[:30]
            placeholder = placeholder.replace(" ", "_")
            return f"input_{placeholder}"

        # Fallback to hash
        hash_str = hashlib.md5(element.selector.encode()).hexdigest()[:8]
        return f"{element_type}_{hash_str}"


def discover_selectors(
    page,
    url: Optional[str] = None,
    include_hidden: bool = False,
) -> Dict[str, str]:
    """
    Convenience function to discover selectors for a page.

    Args:
        page: Playwright page object
        url: Optional URL to navigate to
        include_hidden: Include hidden elements

    Returns:
        Dict mapping semantic names to selector strings
    """
    discovery = SelectorDiscovery(base_url=page.url if not url else url)
    elements = discovery.discover_page(page, url, include_hidden)

    return {name: elem.selector for name, elem in elements.items()}


def discover_selectors_with_metadata(
    page,
    url: Optional[str] = None,
    include_hidden: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """
    Discover selectors with full metadata.

    Args:
        page: Playwright page object
        url: Optional URL to navigate to
        include_hidden: Include hidden elements

    Returns:
        Dict mapping semantic names to element metadata dicts
    """
    discovery = SelectorDiscovery(base_url=page.url if not url else url)
    elements = discovery.discover_page(page, url, include_hidden)

    return {name: elem.to_dict() for name, elem in elements.items()}


def validate_selector(page, selector: str, timeout: int = 5000) -> bool:
    """
    Validate that a selector works on the current page.

    Args:
        page: Playwright page object
        selector: CSS/Playwright selector
        timeout: Timeout in milliseconds

    Returns:
        True if selector finds a visible element
    """
    try:
        locator = page.locator(selector)
        locator.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def suggest_alternative_selectors(
    page,
    failed_selector: str,
    element_description: str,
) -> List[str]:
    """
    Suggest alternative selectors when one fails.

    Args:
        page: Playwright page object
        failed_selector: The selector that failed
        element_description: Description of what element we're looking for

    Returns:
        List of alternative selector suggestions
    """
    alternatives = []

    # Try text-based search
    try:
        locators = page.get_by_text(element_description, exact=False).all()
        for loc in locators[:3]:
            if loc.is_visible():
                # Get attributes to build selector
                test_id = loc.get_attribute("data-testid")
                if test_id:
                    alternatives.append(f"[data-testid='{test_id}']")
                aria = loc.get_attribute("aria-label")
                if aria:
                    alternatives.append(f"[aria-label='{aria}']")
    except Exception:
        pass

    # Try role-based search
    for role in ["button", "link", "textbox", "combobox"]:
        try:
            locators = page.get_by_role(role, name=element_description).all()
            if locators:
                alternatives.append(f"[role='{role}']:has-text('{element_description}')")
        except Exception:
            pass

    return alternatives[:5]  # Return top 5 alternatives
