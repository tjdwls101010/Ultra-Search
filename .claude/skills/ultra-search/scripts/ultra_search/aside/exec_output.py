"""What `aside exec` prints, read when its session transcript is not there to read instead.

The binary prints the run as it goes: each tool call in colour, each call's output dimmed
(`ESC[2m` up to `ESC[0m`), and the agent's messages in plain text. The final message is
everything after the last dimmed block. It has its own blank lines -- headings, tables,
lists -- so a paragraph boundary says nothing about where it starts.
"""
from __future__ import annotations

import re

_DIM = "\x1b[2m"
_RESET = "\x1b[0m"
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_URL = re.compile(r'https?://[^\s"\'<>)\]]+')


def parse_exec_output(text: str) -> tuple[str, list[str]]:
    """The final message, and every URL printed along the way in first-seen order."""
    # 성진: 최종 메시지 경계는 Aside 출력의 색 코드(도구 출력은 흐리게)에 기대는 휴리스틱이다; 세션 상관이 정상이면 거의 쓰이지 않으니, 출력 모양이 바뀌어 이 경로가 자주 쓰이게 되면 그때 다시 잰다.
    start = text.rfind(_DIM)
    if start != -1:
        end = text.find(_RESET, start)
        tail = text[end + len(_RESET):] if end != -1 else ""
    else:
        # No tool ran: everything printed is the message.
        tail = text
    answer = _ANSI.sub("", tail).strip()
    urls: list[str] = []
    for u in _URL.findall(_ANSI.sub("", text)):
        u = u.rstrip('.,")')
        if u not in urls:
            urls.append(u)
    return answer, urls
