"""Repo-level invariants: secrets stay out, build artefacts stay out, and the
things that launch the decks point at files that exist.

Two of these are the reason this file exists at all. A Home Assistant
long-lived access token is a permanent credential with full API access, and
the generated icon sets are thousands of PNGs — both have been kept out of
version control by convention, and convention is exactly what a test is for.

The rest guard the launch path. The LaunchAgent plist and the Taskfile are
where a rename goes unnoticed: nothing imports them, so a wrong path there
surfaces as "the deck didn't come back after reboot".
"""
from __future__ import annotations

import plistlib
import re
import subprocess
from pathlib import Path

import pytest

from conftest import DECKS_DIR, ROOT, STREAMDECK, git_tracked_files

PLIST = DECKS_DIR / "plus-xl" / "com.janvt.streamdeck-xl.plist"
TASKFILE = STREAMDECK / "Taskfile.yml"

# A Home Assistant long-lived token is a JWT, so it always starts this way.
JWT = re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}")
TOKEN_ASSIGNMENT = re.compile(r"HASS_TOKEN\s*=\s*(\S+)")
PLACEHOLDER = "your-long-lived-access-token"

TEXT_SUFFIXES = {".py", ".yaml", ".yml", ".md", ".sh", ".plist", ".h", ".example", ""}


@pytest.fixture(scope="session")
def tracked() -> list[str]:
    return git_tracked_files()


# ── secrets ─────────────────────────────────────────────────────────────────
def test_no_env_file_is_tracked(tracked: list[str]) -> None:
    """`.env` holds the long-lived token. Only the `.example` templates belong
    in git.
    """
    committed = [
        path for path in tracked
        if Path(path).name == ".env" or path.endswith("/.env")
    ]
    assert committed == [], f"credentials file(s) committed: {committed}"


def test_no_secrets_yaml_is_tracked(tracked: list[str]) -> None:
    """ESPHome reads Wi-Fi and API keys from `secrets.yaml`."""
    assert [p for p in tracked if Path(p).name == "secrets.yaml"] == []


def test_no_token_looking_string_is_committed(tracked: list[str]) -> None:
    """Belt and braces: a token can also arrive pasted into a config, a README
    snippet or a log excerpt, not just via a stray `.env`.
    """
    offenders: list[str] = []
    for path in tracked:
        full = ROOT / path
        if full.suffix not in TEXT_SUFFIXES or not full.exists():
            continue
        text = full.read_text(errors="ignore")
        if JWT.search(text):
            offenders.append(f"{path}: JWT-shaped string")
        for value in TOKEN_ASSIGNMENT.findall(text):
            if value not in (PLACEHOLDER, "", "''", '""'):
                offenders.append(f"{path}: HASS_TOKEN={value[:12]}...")
    assert offenders == [], f"possible committed credentials: {offenders}"


@pytest.mark.parametrize("deck", ["plus", "plus-xl"])
def test_env_templates_carry_a_placeholder_not_a_value(deck: str) -> None:
    example = DECKS_DIR / deck / ".env.example"
    assert example.exists(), f"{deck} has no .env.example — `task {deck}:env` copies it"
    text = example.read_text()
    assert f"HASS_TOKEN={PLACEHOLDER}" in text, "template should keep the placeholder"


@pytest.mark.parametrize(
    "path",
    [
        "streamdeck/decks/plus/.env",
        "streamdeck/decks/plus-xl/.env",
        "streamdeck/decks/plus-xl/icons/anything.png",
        "streamdeck/decks/plus/icons/dials/anything.png",
        "m5stack/core/secrets.yaml",
        ".venv-test/lib/x.py",
    ],
)
def test_git_actually_ignores_the_sensitive_paths(path: str) -> None:
    """Asks git, rather than reading `.gitignore` and hoping. A pattern that
    looks right but doesn't match (a leading slash, a missing `**`) is the
    normal way this goes wrong.
    """
    result = subprocess.run(  # noqa: S603
        ["git", "-C", str(ROOT), "check-ignore", "-q", path],
        capture_output=True, check=False,
    )
    assert result.returncode == 0, f"{path} is NOT ignored by git"


def test_no_generated_icons_are_tracked(tracked: list[str]) -> None:
    """Icons are a build artefact — `task icons:all` regenerates them per
    machine, at that deck's native key size.
    """
    assert [p for p in tracked if "/icons/" in p] == []


# ── the launch path ─────────────────────────────────────────────────────────
def test_the_launchagent_plist_is_valid() -> None:
    """launchd rejects a malformed plist quietly: `bootstrap` fails and the deck
    just never starts at login.
    """
    with PLIST.open("rb") as handle:
        plist = plistlib.load(handle)
    assert plist["Label"] == PLIST.stem
    assert plist["RunAtLoad"] is True
    assert plist["ProgramArguments"], "nothing to run"


def test_the_service_restarts_on_failure_but_not_on_a_clean_exit() -> None:
    """`SuccessfulExit: false` is deliberate and load-bearing: with
    CONNECTION_RETRY_ATTEMPTS=-1 the app never exits 0 over an unreachable Home
    Assistant, so a clean exit means "asked to stop" and must not be restarted.
    Dropping the throttle would respawn an unplugged deck in a tight loop.
    """
    with PLIST.open("rb") as handle:
        plist = plistlib.load(handle)
    assert plist["KeepAlive"] == {"SuccessfulExit": False}
    assert plist.get("ThrottleInterval", 0) >= 10


def test_the_service_starts_the_extension_not_the_console_script() -> None:
    """`python -m ext.run` installs the local-action wrappers before handing off
    to the app's `main()`. Under the plain console script the deck still runs,
    but every `mac.*` key and the Mac volume dial become no-ops that Home
    Assistant rejects — a silent, confusing half-failure.
    """
    with PLIST.open("rb") as handle:
        plist = plistlib.load(handle)
    command = " ".join(plist["ProgramArguments"])
    assert "-m ext.run" in command, command
    pythonpath = plist["EnvironmentVariables"]["PYTHONPATH"]
    assert pythonpath.endswith("streamdeck"), f"PYTHONPATH={pythonpath} won't find ext/"


def test_the_taskfile_run_target_also_uses_the_extension() -> None:
    """The foreground path (`task xl:run`) has to match the service path, or
    behaviour differs depending on how the deck was started.
    """
    assert "-m ext.run" in TASKFILE.read_text()


def test_the_plist_paths_match_this_checkout() -> None:
    """Absolute and machine-specific by design (launchd has no cwd). Skipped
    when the repo has been moved or cloned elsewhere, since the mismatch is
    then a property of the machine, not a defect in the file.
    """
    with PLIST.open("rb") as handle:
        plist = plistlib.load(handle)
    workdir = Path(plist["WorkingDirectory"])
    expected = DECKS_DIR / "plus-xl"
    if workdir != expected:
        pytest.skip(f"checkout is at {expected}, plist points at {workdir}")
    assert (workdir / "configuration.yaml").exists()
    assert Path(plist["EnvironmentVariables"]["PYTHONPATH"]) == STREAMDECK


@pytest.mark.parametrize("deck", ["plus", "plus-xl"])
def test_env_templates_enable_infinite_reconnect(deck: str) -> None:
    """The app's own default is 0 retries: one unreachable-HA attempt and it
    exits. Both deployments rely on -1 instead, for reasons the templates spell
    out; losing it means a single HA blip leaves the deck dark.
    """
    text = (DECKS_DIR / deck / ".env.example").read_text()
    assert "CONNECTION_RETRY_ATTEMPTS=-1" in text
    delay = re.search(r"CONNECTION_RETRY_DELAY=(\d+)", text)
    assert delay and int(delay.group(1)) > 0, "a 0 delay busy-loops"


# ── files the tooling names ─────────────────────────────────────────────────
def test_every_path_the_taskfile_names_exists() -> None:
    """A rename that misses the Taskfile fails only when someone runs that
    target — often on the machine that can least afford it.
    """
    import yaml

    # Scan the parsed YAML, not the raw text: the Taskfile is thoroughly
    # commented and the comments name paths illustratively
    # ("decks/<name>/spec.py").
    strings: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, str):
            strings.append(node)
        elif isinstance(node, dict):
            for key, value in node.items():
                walk(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(yaml.safe_load(TASKFILE.read_text()))
    referenced = set(re.findall(
        r"((?:[\w.-]+/)*[\w.-]+\.(?:py|sh|yaml|yml|plist|txt))", "\n".join(strings)))

    def exists(path: str) -> bool:
        # Both are created on the target machine and never committed: the venvs
        # by `task xl:install`, the .env files by `task <deck>:env`.
        if ".venv" in path or Path(path).name.startswith(".env"):
            return True
        if "/" in path:
            # Targets run either from streamdeck/ or, for the repo-wide test
            # targets, from the repo root (`dir: ..`).
            return (STREAMDECK / path).exists() or (ROOT / path).exists()
        # A bare filename is relative to whichever directory that task sets, so
        # accept it if the repo has such a file at all — enough to catch the
        # failure that matters, a file renamed without updating the Taskfile.
        return any(
            candidate for candidate in ROOT.rglob(path)
            if ".venv" not in candidate.parts
        )

    missing = sorted(path for path in referenced if not exists(path))
    assert missing == [], f"Taskfile.yml names paths that do not exist: {missing}"


def test_every_tracked_python_file_compiles(tracked: list[str]) -> None:
    """Cheap syntax gate over the whole repo, including the scripts nothing
    imports (`generate_icons.py`, the patcher, each deck's `spec.py`).
    """
    for path in tracked:
        if path.endswith(".py"):
            source = (ROOT / path).read_text()
            compile(source, path, "exec")


@pytest.mark.parametrize("deck", ["plus", "plus-xl"])
def test_each_deck_has_the_files_its_tooling_expects(deck: str) -> None:
    for name in ("configuration.yaml", "spec.py", ".env.example"):
        assert (DECKS_DIR / deck / name).exists(), f"decks/{deck}/{name} is missing"
