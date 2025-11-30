"""Tests for HTML rendering helper."""

from bot.run import _plain_text_to_html


def test_plain_text_to_html_sections_and_links() -> None:
    body = "Header:\n• Bullet 1\n• Bullet 2\n\nParagraph with **bold** and [link](https://example.com)"
    html = _plain_text_to_html(body)
    assert "<h3" in html and "Header" in html
    assert "<ul>" in html and "Bullet 1" in html
    assert "<strong>bold</strong>" in html
    assert '<a href="https://example.com">link</a>' in html
