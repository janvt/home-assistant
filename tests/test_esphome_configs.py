"""The ESPHome device configs under `m5stack/`.

These are 1300-line single-file configs full of inline C++ lambdas, and the
feedback loop on them is brutal: a typo is found by the compiler minutes into a
flash, or worse by the device failing to boot on a shelf. Everything here is
the cheap subset of that feedback, available in milliseconds:

  * the file parses, and no mapping key is silently overwritten by a later
    duplicate (YAML's quietest footgun in a file this size);
  * every `${substitution}` is defined;
  * every `id(...)` a lambda dereferences is actually declared — otherwise it's
    a C++ compile error found at flash time;
  * every `includes:` header exists (this caught a stale reference left behind
    by a directory rename);
  * no credential is inline — Wi-Fi and API keys come from `!secret`.

`test_esphome_validates_the_config` runs ESPHome's own validator, which is far
stronger than any of the above but needs the `esphome` package and the network
(one config pulls an external component from GitHub). It skips when ESPHome
isn't installed; CI runs it in a dedicated job.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from conftest import M5STACK

CONFIGS = sorted(M5STACK.glob("*/*.yaml"))
IDS = [str(p.relative_to(M5STACK)) for p in CONFIGS]

# The complete set of secrets these devices may reference. Kept explicit so a
# typo'd name is a test failure rather than an ESPHome error at flash time,
# and so the list of credentials the fleet needs is written down somewhere.
KNOWN_SECRETS = {
    "wifi_ssid", "wifi_password", "m5fallbackpassword",
    "m5core2encryption", "m5cores3encryption", "m5dialencryption",
}

# Fields that must never hold a literal value.
CREDENTIAL_FIELDS = ("password", "key", "psk")

# Known gaps against CURRENT ESPHome, recorded rather than hidden: both display
# configs declare `model: M5CORE2` under `display.mipi_spi`, and that model now
# requires an explicit `psram:` block, which neither file has. These flashed
# fine on the ESPHome version they were written against, so this is version
# drift rather than a typo — and the right block differs per chip (the Core2 is
# an ESP32 with quad PSRAM, the CoreS3 an ESP32-S3 with octal), so it needs a
# deliberate decision per device rather than a blanket fix. xfail is
# non-strict: adding `psram:` makes these pass without any change here.
_PSRAM = "display model M5CORE2 now requires an explicit `psram:` component"
KNOWN_VALIDATION_GAPS = {
    "core/m5-core.yaml": _PSRAM,
    "cores3/m5-cores3.yaml": _PSRAM,
}


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps ESPHome's tags legible and rejects duplicate keys.

    Unknown tags become the string `!tag value` so assertions can still see
    which secret a field pulls from. Duplicate keys raise: PyYAML's default is
    last-one-wins, which in a file this long means an override you never
    intended and cannot see.
    """


def _tag(loader: yaml.Loader, suffix: str, node: yaml.Node) -> str:
    value = getattr(node, "value", "")
    return f"!{suffix} {value}".strip() if isinstance(value, str) else f"!{suffix}"


def _no_duplicate_keys(loader: yaml.Loader, node: yaml.MappingNode) -> dict:
    seen: set = set()
    for key_node, _value in node.value:
        key = loader.construct_object(key_node)
        if isinstance(key, (str, int, float, bool)):
            if key in seen:
                raise AssertionError(
                    f"duplicate key {key!r} at line {key_node.start_mark.line + 1} "
                    f"— the later value silently wins",
                )
            seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node)


_Loader.add_multi_constructor("!", _tag)
_Loader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicate_keys,
)


@pytest.fixture(params=CONFIGS, ids=IDS)
def config(request: pytest.FixtureRequest) -> Path:
    return request.param


def _load(path: Path) -> dict:
    return yaml.load(path.read_text(), Loader=_Loader)


def _walk(node, path=()):  # noqa: ANN001, ANN202
    yield path, node
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, (*path, key))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _walk(item, (*path, index))


def test_there_are_configs_to_check() -> None:
    assert CONFIGS, f"no ESPHome YAML found under {M5STACK}"


def test_parses_without_duplicate_keys(config: Path) -> None:
    document = _load(config)
    assert isinstance(document, dict) and document


def test_declares_the_core_components(config: Path) -> None:
    """Anything without these can't be reached after flashing: no `api:` means
    no Home Assistant, no `ota:` means the next update needs a USB cable.
    """
    document = _load(config)
    assert "esphome" in document and document["esphome"].get("name")
    assert "esp32" in document, "no platform block"
    assert "wifi" in document
    assert "api" in document, "device would not be reachable from Home Assistant"
    assert "ota" in document, "no OTA — reflashing would need a cable"


def test_substitutions_are_all_defined(config: Path) -> None:
    text = config.read_text()
    defined = set((_load(config).get("substitutions") or {}))
    used = set(re.findall(r"\$\{(\w+)\}", text))
    assert sorted(used - defined) == [], f"undefined substitutions in {config.name}"


def test_every_referenced_id_is_declared(config: Path) -> None:
    """`id(foo)` inside a lambda is C++: an undeclared name is a compile error
    that only shows up several minutes into a flash.
    """
    text = config.read_text()
    declared = set(re.findall(r"^\s*(?:-\s*)?id:\s*([a-zA-Z_]\w*)\s*$", text, re.M))
    referenced = set(re.findall(r"\bid\(([a-zA-Z_]\w*)\)", text))
    assert sorted(referenced - declared) == [], (
        f"{config.name} dereferences ids it never declares"
    )


def test_included_headers_exist(config: Path) -> None:
    """`includes:` is resolved relative to the YAML file. A stale name here is
    a hard ESPHome error — and it is exactly what a directory rename leaves
    behind (the Core config carried `m5core2_helpers.h` after the folder became
    `core/` and the header became `m5core_helpers.h`).
    """
    includes = (_load(config).get("esphome") or {}).get("includes") or []
    missing = [name for name in includes if not (config.parent / name).exists()]
    assert missing == [], (
        f"{config.name} includes files that do not exist: {missing} "
        f"(present: {sorted(p.name for p in config.parent.glob('*.h'))})"
    )


def test_credentials_come_from_secrets(config: Path) -> None:
    """No Wi-Fi password or API key inline — this repo is public-ish and the
    configs are the kind of file that gets pasted into an issue.
    """
    inline = [
        "/".join(str(part) for part in path)
        for path, value in _walk(_load(config))
        if path and path[-1] in CREDENTIAL_FIELDS and isinstance(value, str)
        and not value.startswith(("!secret", "${"))
    ]
    assert inline == [], f"{config.name} has literal credentials at: {inline}"


def test_secret_names_are_known(config: Path) -> None:
    used = set(re.findall(r"!secret\s+(\w+)", config.read_text()))
    assert sorted(used - KNOWN_SECRETS) == [], (
        f"{config.name} uses secrets not in KNOWN_SECRETS — add them there (and "
        f"to secrets.yaml on the machine that flashes) or fix the typo"
    )


def test_the_helper_headers_are_self_contained(config: Path) -> None:
    """Each `includes:` header is compiled straight into the generated sketch,
    so it needs its own include guard or a second inclusion redefines
    everything.
    """
    for name in (_load(config).get("esphome") or {}).get("includes") or []:
        header = config.parent / name
        if not header.exists():
            continue  # reported by test_included_headers_exist
        text = header.read_text()
        assert "#pragma once" in text or "#ifndef" in text, f"{name} has no include guard"


# ── ESPHome's own validator ─────────────────────────────────────────────────
@pytest.mark.esphome
def test_esphome_validates_the_config(config: Path, tmp_path: Path) -> None:
    """The real thing: component schemas, pin conflicts, id types, the lot.

    Run against a copy with stub secrets, so it neither reads real credentials
    nor writes build artefacts into the repo.
    """
    pytest.importorskip("esphome", reason="pip install esphome to run this")
    gap = KNOWN_VALIDATION_GAPS.get(str(config.relative_to(M5STACK)))
    if gap:
        pytest.xfail(gap)

    work = tmp_path / config.parent.name
    work.mkdir(parents=True)
    for source in [config, *config.parent.glob("*.h")]:
        (work / source.name).write_bytes(source.read_bytes())
    # 32 bytes, base64 — the api encryption schema checks the length.
    (work / "secrets.yaml").write_text(
        'wifi_ssid: "ci-ssid"\n'
        'wifi_password: "ci-password"\n'
        'm5fallbackpassword: "ci-fallback"\n'
        + "".join(
            f'{name}: "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="\n'
            for name in sorted(KNOWN_SECRETS)
            if name.endswith("encryption")
        ),
    )
    # Retried once on a network-shaped failure. This step reaches out for an
    # external component (a GitHub clone) and one SVG per `mdi:` image, and a
    # single dropped fetch was observed turning a valid config into a failure.
    # Only network wording is retried — a schema error fails on the first pass.
    for attempt in (1, 2):
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "esphome", "config", config.name],
            cwd=work, capture_output=True, text=True, check=False, timeout=900,
        )
        output = result.stdout + result.stderr
        transient = any(
            phrase in output
            for phrase in ("Download failed", "Error downloading", "HTTP Error",
                           "Connection", "timed out", "Temporary failure")
        )
        if result.returncode == 0 or not transient or attempt == 2:
            break
    assert result.returncode == 0, (
        f"esphome config failed for {config.name}:\n"
        f"{result.stdout[-3000:]}\n{result.stderr[-1500:]}"
    )
