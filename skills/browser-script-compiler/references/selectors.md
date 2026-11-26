# Choosing locators that survive site updates

Order of preference (most to least stable). Sites change their CSS class names constantly (build-hashed classes like `.css-1x2y3z`), but rarely change what a control *is* or *says*.

1. **Role + accessible name**: `page.get_by_role("button", name="Send")`. Matches how users and screen readers see the page.
2. **Label / placeholder**: `page.get_by_label("Email")`, `page.get_by_placeholder("Search")`.
3. **Test ids** if the site has them: `page.get_by_test_id("send-button")` (`data-testid`). Stable by intent, but can still be renamed.
4. **Visible text**: `page.get_by_text("Download", exact=True)`.
5. **Structural CSS** tied to semantics: `main article h2`, `form[action*='search'] input`.
6. **Generated class names or long XPath**: last resort, and note it in a comment so the repairer expects breakage.

## Make locators tolerant, not vague
- Give each step an **ordered fallback list** (first visible wins), as `scripts/sites.json` does in the image-generation skill. Cheap, and repairs become one-line edits to a list.
- Case-insensitive partial matches (`[aria-label*='send' i]`) survive small wording changes.
- Scope to a region first (`page.get_by_role("main")`, `dialog`) so a duplicate button elsewhere is not hit.

## Waiting
- Wait for the **result**, not time: an element visible, a URL pattern (`page.wait_for_url`), a network response (`page.expect_response`), or a "busy" indicator disappearing.
- For streaming UIs (chat, generation), wait for the busy/stop control to vanish AND the result to stop changing for a couple of polls.
- Rich-text editors (`contenteditable`): click, then `page.keyboard.insert_text(text)`. `locator.fill` fails on some of them; per-key typing is slow.

## Getting locators cheaply during exploration
Read the accessibility snapshot (role + name per element) instead of screenshots. In a script, `page.locator("body").aria_snapshot()` prints the same tree; `generate_image.py --inspect` shows the pattern.
