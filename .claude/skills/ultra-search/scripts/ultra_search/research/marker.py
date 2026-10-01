"""The line every delegated prompt carries: what research may not do, and which run asked.

Aside's CLI never reports which session it created, and matching on the prompt text cannot
tell two parallel runs of the same question apart -- picking the wrong one reports someone
else's answer as yours. So each prompt carries this run's marker, and the session that opens
with it is the run's.
"""
from __future__ import annotations

PREFIX = "ultra-search:"

#: Said in every prompt: the browsing agent acts as the user, in their logged-in browser.
SCOPE = "Read-only research: do not post, purchase, sign up, or change account settings."


def marker_for(run_id: str) -> str:
    return f"{PREFIX}{run_id}"


def decorate_prompt(prompt: str, marker: str) -> str:
    """Append the research scope and the correlation marker to a prompt.

    The marker goes last and says what it is, so the agent reads it as bookkeeping rather
    than as part of the task; a run was measured answering the question correctly with it
    attached.
    """
    return f"{prompt}\n\n{SCOPE}\n\n({marker} — ignore this line)"


def run_id_in(prompt: str) -> str | None:
    """The run id a prompt's marker names, if this tool wrote the prompt."""
    if PREFIX not in prompt:
        return None
    return prompt.split(PREFIX, 1)[1].split(" ", 1)[0].strip(")\n") or None
