#!/usr/bin/env python3
"""Strip [[S5_*]] or [[S7_*]] marked regions from asm text."""
import re, sys
from pathlib import Path

def apply(text: str, screen: str) -> str:
    if screen == "s5":
        text = re.sub(r"; \[\[S7_START\]\]\n.*?; \[\[S7_END\]\]\n?", "", text, flags=re.S)
        text = text.replace("; [[S5_START]]\n", "").replace("; [[S5_END]]\n", "")
    else:
        text = re.sub(r"; \[\[S5_START\]\]\n.*?; \[\[S5_END\]\]\n?", "", text, flags=re.S)
        text = text.replace("; [[S7_START]]\n", "").replace("; [[S7_END]]\n", "")
    return text

if __name__ == "__main__":
    screen = sys.argv[1]
    src = Path(sys.argv[2]).read_text()
    Path(sys.argv[3]).write_text(apply(src, screen))
