from app.services.speech import speech_text


def test_speech_text_strips_markdown_formatting():
    assert (
        speech_text("# Heading\n- **Bold** item\n1. `inline code`\n[Docs](https://example.com)")
        == "Heading Bold item inline code Docs"
    )


def test_speech_text_omits_fenced_code():
    assert speech_text("Before\n```python\nprint('hello')\n```\nAfter") == ("Before Code block omitted. After")


def test_speech_text_handles_images_and_links():
    assert speech_text("![Diagram](image.png) and [guide](guide.md)") == "Diagram and guide"


def test_speech_text_handles_malformed_markdown():
    text = "[" + "\\" * 40
    assert speech_text(text) == text


def test_speech_text_handles_long_adversarial_input():
    text = "[" + "\\" * 10000
    assert speech_text(text) == text
