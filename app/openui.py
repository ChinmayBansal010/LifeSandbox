"""OpenUI Lang prompt built from @openuidev/react-ui's chat component library."""

from pathlib import Path

OPENUI_SYSTEM_PROMPT = Path(__file__).with_name("openui_prompt.txt").read_text(encoding="utf-8")
