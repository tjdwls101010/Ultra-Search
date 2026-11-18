"""The account's own model settings, as Aside stores them on disk.

The CLI has no command that says whether the model a session will run on can be reached: a `search` on a default model
whose provider credential has expired is accepted, starts a session and fails in it at once with `Authentication failed`.
Aside records that state in its private files, so it is read there -- and only the state: the credentials file holds the
provider's tokens, and nothing else of it is kept or reported.
"""
from __future__ import annotations

import json

from ultra_search.aside.sessions import ACCOUNT, aside_home

#: The two states Aside's own schema defines for a provider credential (`modelProviderStateSchema` in the CLI).
CONNECTED, EXPIRED = "active", "auth-expired"


def model_access() -> dict:
    """{ok, detail, fix?, note?}: whether the provider of the account's default model is connected.

    Fails only on what Aside wrote: a stored credential whose state is the expired one. A file missing, unreadable or
    shaped otherwise, and a state outside the two Aside defines, pass with a note saying it was not checked -- these are
    Aside's private files, and failing on their format would fail an environment every command works in. Only a known
    state is ever quoted: an unknown value in that field could be anything the file holds.
    """
    try:
        model = _read("settings.json").get("defaultModel")
        provider, model_id = model["provider"], model["modelId"]
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        return _unchecked("the account's default model could not be read from Aside's settings")
    name = f"{provider}/{model_id}"
    try:
        state = _read("credentials.json")[provider]["state"]
        if not isinstance(state, str):
            raise TypeError(provider)
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        # Aside's built-in models have no stored credential; signing in to Aside is what they need.
        # 성진: a built-in default model under a signed-out account passes here unchecked (sign-in was not made a doctor
        # failure, and a built-in model's failure when signed out was never measured); revisit if that is seen to fail.
        return _unchecked(f"no stored credential state for {provider} was found", detail=f"default model {name}")
    if state == CONNECTED:
        return {"ok": True, "detail": f"default model {name}; its provider is connected"}
    if state != EXPIRED:
        return _unchecked(f"the stored credential for {provider} is in a state this check does not know",
                          detail=f"default model {name}")
    return {
        "ok": False,
        "detail": f"default model {name}; Aside records its provider credential as {EXPIRED}",
        "fix": f"Reconnect {provider} in Aside, or pass `--model` with a provider that is connected. "
               "`fetch`, `map` and `crawl` do not use a model.",
    }


def _read(name: str) -> dict:
    with open(aside_home() / ACCOUNT / name, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(name)
    return data


def _unchecked(why: str, *, detail: str = "not checked") -> dict:
    return {"ok": True, "detail": detail, "note": f"not checked: {why}"}
