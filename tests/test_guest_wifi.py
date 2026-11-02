"""The guest Wi-Fi rotation: `packages/guest_wifi.yaml`, the script, the automation
and the guest room display (`guest-eink/`).

Four files in two systems agree on names that nothing checks at runtime. The
automation watches an entity the ESPHome device creates, the script writes to
another one, and the script calls rest_commands defined in a package. Rename any
of them and nothing errors: the password simply stops rotating, or rotates
without the display ever showing the new one.

The size budget is the quieter failure. The display draws the QR code at a fixed
10 px per module, laid out for QR version 3. A password that pushes the payload
to version 4 makes the code 40 px wider and taller, and it runs into the Wi-Fi
name and password text under it. The panel still renders, just wrong.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from conftest import ROOT

PACKAGE = ROOT / "packages" / "guest_wifi.yaml"
SCRIPT = ROOT / "scripts" / "rotate_guest_wifi_password.yaml"
AUTOMATION = ROOT / "automations" / "guest_wifi_on_guest_name_change.yaml"
DISPLAY = ROOT / "guest-eink" / "guest-eink.yaml"

# The live SSID is a text entity on the display, not in any file here. Update this
# if the guest network is renamed.
GUEST_SSID = "SchmatzGuest"

# Byte-mode capacity of a version 3 QR code at ECC level L (the display uses
# `ecc: LOW`).
QR_V3_L_BYTES = 53


class _Loader(yaml.SafeLoader):
    """SafeLoader that turns `!secret x` / ESPHome tags into plain strings."""


_Loader.add_multi_constructor(
    "!", lambda loader, suffix, node: f"!{suffix} {getattr(node, 'value', '')}".strip(),
)


def _load(path: Path) -> Any:
    return yaml.load(path.read_text(), Loader=_Loader)


def _script() -> dict[str, Any]:
    return _load(SCRIPT)["rotate_guest_wifi_password"]


def _strings(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _strings(v)]
    return []


def _display_entity_suffixes() -> set[str]:
    """`<device friendly name>_<entity name>`, slugged the way HA builds entity ids.

    HA may prefix the area (`guest_bedroom_...`), so ids are matched on the suffix.
    """
    display = _load(DISPLAY)
    device = display["substitutions"]["friendly_name"]
    names = [e["name"] for e in display.get("text") or [] if "name" in e]
    slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")  # noqa: E731
    return {f"{slug(device)}_{slug(name)}" for name in names}


def test_the_longest_generated_password_keeps_the_qr_at_version_3() -> None:
    """Worst case from the script's own word lists, escaped as the display escapes it."""
    template = _script()["sequence"][0]["variables"]["new_password"]
    lists = [re.findall(r"'([^']+)'", body) for body in re.findall(r"\[([^\]]+)\]", template)]
    assert len(lists) == 2, "expected an adjective list and a noun list"
    nouns, adjectives = lists
    longest = f"{max(adjectives, key=len)}-{max(nouns, key=len)}-{max(nouns, key=len)}-99"
    escape = lambda s: re.sub(r'([\\;,:"])', r"\\\1", s)  # noqa: E731
    payload = f"WIFI:T:WPA;S:{escape(GUEST_SSID)};P:{escape(longest)};;"
    assert len(payload.encode()) <= QR_V3_L_BYTES, (
        f"{longest!r} makes a {len(payload)}-byte payload; QR v3-L holds {QR_V3_L_BYTES}"
    )


def test_the_script_writes_the_displays_password_entity() -> None:
    targets = [
        step["target"]["entity_id"]
        for step in _script()["sequence"]
        if step.get("action") == "text.set_value"
    ]
    assert targets, "the script never pushes the password to the display"
    suffixes = _display_entity_suffixes()
    for entity in targets:
        assert any(entity.endswith(s) for s in suffixes), (
            f"{entity} is not a text entity the display declares ({sorted(suffixes)})"
        )


def test_the_automation_watches_the_displays_guest_name() -> None:
    automation = _load(AUTOMATION)
    watched = {t["entity_id"] for t in automation["triggers"]}
    suffixes = _display_entity_suffixes()
    assert all(any(e.endswith(s) for s in suffixes) for e in watched), watched
    assert all(e.endswith("_guest_name") for e in watched), watched


def test_the_automation_calls_a_script_that_exists() -> None:
    called = {
        s.removeprefix("script.")
        for s in _strings(_load(AUTOMATION)["actions"])
        if s.startswith("script.")
    }
    assert called == set(_load(SCRIPT)), called


def test_the_script_only_uses_rest_commands_the_package_defines() -> None:
    used = {
        step["action"].removeprefix("rest_command.")
        for step in _script()["sequence"]
        if str(step.get("action", "")).startswith("rest_command.")
    }
    defined = set(_load(PACKAGE)["rest_command"])
    assert used and used <= defined, f"undefined rest_commands: {sorted(used - defined)}"


def test_the_login_credentials_stay_in_secrets() -> None:
    login = _load(PACKAGE)["rest_command"]["unifi_login"]
    assert str(login["payload"]).startswith("!secret "), "login body must come from secrets.yaml"


def test_the_automation_brings_the_display_back_to_the_welcome_page() -> None:
    """A message left on the panel would otherwise hide the new guest and the new
    QR code: the display only redraws the welcome page while it is showing.
    """
    display = _load(DISPLAY)
    slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")  # noqa: E731
    device = slug(display["substitutions"]["friendly_name"])
    selects = {f"{device}_{slug(s['name'])}": s for s in display.get("select") or [] if "name" in s}
    page_steps = [
        step for step in _load(AUTOMATION)["actions"]
        if step.get("action") == "select.select_option"
    ]
    assert page_steps, "the automation never switches the display's page"
    step = page_steps[0]
    entity = step["target"]["entity_id"]
    matches = [s for suffix, s in selects.items() if entity.endswith(suffix)]
    assert matches, f"{entity} is not a select the display declares ({sorted(selects)})"
    assert step["data"]["option"] in matches[0]["options"], (
        f"{step['data']['option']!r} is not an option of {entity}"
    )
    assert _load(AUTOMATION)["actions"][0] == step, (
        "switch the page before anything else, so a failed rotation still shows the welcome card"
    )


CALENDAR = ROOT / "automations" / "guest_calendar_stays.yaml"


def test_a_check_in_after_a_display_reboot_still_fires() -> None:
    """After a reboot the display reports an empty name as `unknown`, not "". A
    trigger that excludes `unknown` silently skips the next check-in: no new Wi-Fi
    password, guest network left off. `unavailable` must stay excluded (reboots and
    Wi-Fi blips are not guest changes).
    """
    automation = _load(AUTOMATION)
    for trigger in automation["triggers"]:
        for key in ("not_from", "not_to", "from", "to"):
            values = trigger.get(key) or []
            values = [values] if isinstance(values, str) else values
            assert "unknown" not in values, f"trigger {key} excludes 'unknown'"
        assert "unavailable" in trigger.get("not_from", []), "a reboot would fire it"
    checkout = automation["actions"][1]["if"][0]
    states = checkout["state"] if isinstance(checkout["state"], list) else [checkout["state"]]
    assert {"", "unknown"} <= set(states), "check-out must treat unknown as an empty name"


def test_the_calendar_automation_only_drives_entities_the_display_has() -> None:
    display = _load(DISPLAY)
    slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")  # noqa: E731
    device = slug(display["substitutions"]["friendly_name"])
    declared = {
        f"{device}_{slug(entity['name'])}": entity
        for platform in ("text", "select")
        for entity in display.get(platform) or []
        if "name" in entity
    }
    calendar = _load(CALENDAR)
    ids = {
        step["target"]["entity_id"]
        for step in _walk_steps(calendar["actions"])
        if str(step.get("action", "")).startswith(("text.", "select."))
    } | {
        m for s in _strings(calendar["variables"])
        for m in re.findall(r"states\('((?:text|select)\.\w+)'\)", s)
    }
    assert ids, "the calendar automation touches no display entity"
    for entity in ids:
        assert any(entity.endswith(suffix) for suffix in declared), (
            f"{entity} is not an entity the display declares ({sorted(declared)})"
        )
    page = next(e for suffix, e in declared.items() if suffix.endswith("_page"))
    options = {
        s["data"]["option"]
        for s in _walk_steps(calendar["actions"])
        if s.get("action") == "select.select_option"
    }
    assert options and options <= set(page["options"]), options


def test_every_calendar_profile_has_a_farewell_the_display_can_render() -> None:
    """The prefix regex and the farewells mapping must name the same profiles, and
    the defaults go through the Message page's fonts (GF_Latin_Core: ASCII is safe).
    """
    calendar = _load(CALENDAR)
    farewells = calendar["variables"]["farewells"]
    prefixes = set(re.search(r"\(([A-Z|]+)\)", calendar["variables"]["match"]).group(1).split("|"))
    assert prefixes == set(farewells), (prefixes, set(farewells))
    for profile, text in farewells.items():
        assert text and text.isascii(), f"{profile}: {text!r}"


def _walk_steps(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        return [node] + [s for v in node.values() for s in _walk_steps(v)]
    if isinstance(node, list):
        return [s for v in node for s in _walk_steps(v)]
    return []
