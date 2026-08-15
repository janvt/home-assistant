"""`python -m ext.selftest` — verify the extension against the installed app.

Runs off-hardware with stub decks and a stubbed macOS bridge, so it is safe to
run any time (it never changes the real volume). Plain unittest so it needs no
dependency beyond what the deck venv already has.

The point of these tests is not the handlers — those are three lines each — it
is the SEAMS. If an upstream upgrade moves `call_service`, renames
`handle_changes`, or stops routing dial turns through `call_service`, this fails
loudly here instead of silently sending `mac.volume_set` to Home Assistant.
"""
from __future__ import annotations

import asyncio
import subprocess
import unittest
from typing import Any
from unittest import mock

import home_assistant_streamdeck_yaml as app

from . import actions, state, wrap
from . import mac as mac_mod

ICON = "/dev/null"  # never actually read; render is stubbed out where needed


def setUpModule() -> None:
    """Install once for the whole module.

    Previously each class re-installed, which both nested the wrappers and left
    the suite order-dependent — `Handlers` runs first alphabetically and used to
    execute against an unwrapped app.
    """
    wrap.install()


def tearDownModule() -> None:
    wrap.uninstall()


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, payload: str) -> None:
        self.sent.append(payload)


class FakeDeck:
    """Just enough StreamDeck to satisfy update_dial()/update_key_image()."""

    def __init__(self) -> None:
        self.strip_writes: list[tuple[int, int, int]] = []
        self.key_writes: list[int] = []

    def key_count(self) -> int:
        return 4

    def dial_count(self) -> int:
        return 2

    def is_visual(self) -> bool:
        return True

    def touchscreen_image_format(self) -> dict[str, Any]:
        return {"size": (400, 100), "rotation": 0}

    def key_image_format(self) -> dict[str, Any]:
        return {"size": (72, 72)}

    def set_touchscreen_image(self, _img: bytes, x: int, y: int, width: int = 0, height: int = 0) -> None:  # noqa: ANN001
        self.strip_writes.append((x, y, width))

    def set_key_image(self, key: int, _img: bytes | None) -> None:
        self.key_writes.append(key)

    def reset(self) -> None:
        pass

    # update_key_image() guards the HID write with `with deck:`
    def __enter__(self) -> FakeDeck:
        return self

    def __exit__(self, *_: object) -> bool:
        return False


def make_config(buttons: list = (), dials: list = ()) -> app.Config:  # noqa: ANN001
    page = app.Page(name="t", buttons=list(buttons), dials=list(dials))
    cfg = app.Config(pages=[page])
    cfg._is_on = True  # noqa: SLF001
    cfg.current_page().sort_dials()
    return cfg


def volume_dial() -> app.Dial:
    return app.Dial(
        entity_id="mac.volume",
        dial_event_type="TURN",
        state_attribute="level",
        service="mac.volume_set",
        service_data={"level": "{{ dial_value() | int }}"},
        attributes={"min": 0, "max": 100, "step": 2},
        icon=ICON,
    )


class SeamGuard(unittest.TestCase):
    def test_install_accepts_the_installed_version(self) -> None:
        """The signature guard must pass against whatever is in site-packages."""
        self.assertTrue(asyncio.iscoroutinefunction(app.call_service))

    def test_guard_rejects_a_moved_seam(self) -> None:
        with mock.patch.object(app, "call_service", lambda *a, **k: None):  # noqa: ARG005
            with self.assertRaises(RuntimeError) as ctx:
                wrap._check(app)  # noqa: SLF001
            self.assertIn("call_service", str(ctx.exception))


class Interception(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.ws = FakeWS()
        self.deck = FakeDeck()

    async def test_button_local_action_never_reaches_hass(self) -> None:
        btn = app.Button(service="mac.volume_set", service_data={"level": 33})
        with mock.patch.object(actions.mac, "set_volume") as set_volume, \
             mock.patch.object(actions.mac, "read_volume", return_value=(33, False)):
            await app._handle_key_press(  # noqa: SLF001
                self.ws, {}, make_config([btn]), btn, self.deck, is_long_press=False,
            )
        set_volume.assert_called_once_with(33)
        self.assertEqual(self.ws.sent, [], "local action leaked to Home Assistant")

    async def test_hass_action_still_reaches_hass(self) -> None:
        btn = app.Button(service="light.toggle", entity_id="light.x")
        state_ = {"light.x": {"state": "on", "attributes": {}}}
        await app._handle_key_press(  # noqa: SLF001
            self.ws, state_, make_config([btn]), btn, self.deck, is_long_press=False,
        )
        self.assertEqual(len(self.ws.sent), 1)
        self.assertIn("light", self.ws.sent[0])

    async def test_long_press_local_action(self) -> None:
        btn = app.Button(
            service="light.toggle",
            entity_id="light.x",
            long_press={"service": "mac.volume_mute"},
        )
        state_ = {"light.x": {"state": "on", "attributes": {}}}
        with mock.patch.object(actions.mac, "read_volume", return_value=(40, False)), \
             mock.patch.object(actions.mac, "set_muted") as set_muted:
            await app._handle_key_press(  # noqa: SLF001
                self.ws, state_, make_config([btn]), btn, self.deck, is_long_press=True,
            )
        set_muted.assert_called_once_with(True)
        self.assertEqual(self.ws.sent, [])

    async def test_dial_turn_renders_template_and_stays_local(self) -> None:
        dial = volume_dial()
        cfg = make_config([], [dial])
        st = {"mac.volume": {"state": "44", "attributes": {"level": 44, "muted": False}}}
        dial.update_attributes(st["mac.volume"])
        with mock.patch.object(actions.mac, "set_volume") as set_volume, \
             mock.patch.object(actions.mac, "read_volume", return_value=(50, False)):
            await app.handle_dial_event(
                self.ws, st, cfg, (dial, None), self.deck,
                app.DialEventType.TURN, 3,  # +3 ticks * step 2 = 50
            )
        set_volume.assert_called_once_with(50)
        self.assertEqual(self.ws.sent, [])


class SyntheticState(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        # mock.patch has already put the real get_states back, but _originals may
        # still hold the stub captured below — drop it and re-wrap cleanly so
        # later tests in the module are unaffected.
        wrap._installed = False  # noqa: SLF001
        wrap._originals.clear()  # noqa: SLF001
        wrap.install()

    async def test_get_states_seeds_synthetic_entities(self) -> None:
        # Order matters: uninstall FIRST so the install() below captures the stub
        # as its original. Patching after installing would leave the wrapper
        # closed over the real get_states, which then tries to talk to FakeWS.
        wrap.uninstall()
        with mock.patch.object(state.mac, "read_volume", return_value=(7, True)), \
             mock.patch.object(app, "get_states", new=_fake_get_states):
            wrap.install()  # wraps the stub
            got = await app.get_states(FakeWS())
        self.assertIn("mac.volume", got)
        self.assertEqual(got["mac.volume"]["state"], "7")
        self.assertIs(got["mac.volume"]["attributes"]["muted"], True)
        self.assertIn("light.real", got, "real HA state was dropped")

    async def test_publish_updates_the_dial_through_the_app(self) -> None:
        """An external volume change must move the dial via the app's own path."""
        dial = volume_dial()
        cfg = make_config([], [dial])
        deck = FakeDeck()
        st: dict[str, Any] = {
            "mac.volume": {"state": "10", "attributes": {"level": 10, "muted": False}},
        }
        dial.update_attributes(st["mac.volume"])
        self.assertEqual(dial.get_attributes()["state"], 10)

        with mock.patch.object(app.Dial, "render_lcd_image", _blank_image):
            state.publish(
                "mac.volume",
                {"state": "80", "attributes": {"level": 80, "muted": False}},
                st, cfg, deck,
            )
        self.assertEqual(dial.get_attributes()["state"], 80)
        self.assertEqual(st["mac.volume"]["state"], "80")
        self.assertTrue(deck.strip_writes, "dial was not redrawn")


class Poller(unittest.IsolatedAsyncioTestCase):
    """The poller must notice external changes but never fight the user's turn."""

    async def asyncSetUp(self) -> None:
        self.dial = volume_dial()
        self.cfg = make_config([], [self.dial])
        self.deck = FakeDeck()
        self.st: dict[str, Any] = {
            "mac.volume": {"state": "10", "attributes": {"level": 10, "muted": False}},
        }
        self.dial.update_attributes(self.st["mac.volume"])
        state._last.clear()  # noqa: SLF001
        state._settle_until.clear()  # noqa: SLF001
        state._last["mac.volume"] = dict(self.st["mac.volume"])  # noqa: SLF001
        self._render = mock.patch.object(app.Dial, "render_lcd_image", _blank_image)
        self._render.start()
        self._interval = mock.patch.object(state, "POLL_INTERVAL", 0.01)
        self._interval.start()

    async def asyncTearDown(self) -> None:
        self._render.stop()
        self._interval.stop()

    async def _run_poller_briefly(self) -> None:
        stop = state.run_poller(self.st, self.cfg, self.deck)
        await asyncio.sleep(0.05)
        await stop()

    async def test_external_change_moves_the_dial(self) -> None:
        """e.g. the user pressed the Mac's own volume keys."""
        with mock.patch.object(state.mac, "read_volume", return_value=(70, False)):
            await self._run_poller_briefly()
        self.assertEqual(self.dial.get_attributes()["state"], 70)
        self.assertTrue(self.deck.strip_writes)

    async def test_unchanged_value_causes_no_redraw(self) -> None:
        with mock.patch.object(state.mac, "read_volume", return_value=(10, False)):
            await self._run_poller_briefly()
        self.assertEqual(self.deck.strip_writes, [], "redrew on an unchanged value")

    async def test_settle_window_suppresses_polling(self) -> None:
        """After our own write, a stale read must not yank the dial back."""
        state.settle("mac.volume", 5.0)
        with mock.patch.object(state.mac, "read_volume", return_value=(99, False)) as rv:
            await self._run_poller_briefly()
        rv.assert_not_called()
        self.assertEqual(self.dial.get_attributes()["state"], 10)

    async def test_poller_survives_a_failing_read(self) -> None:
        with mock.patch.object(state.mac, "read_volume", side_effect=OSError("boom")):
            await self._run_poller_briefly()  # must not raise or exit early

    async def test_volume_set_arms_settle_and_returns_a_hint(self) -> None:
        """The handler arms the settle window and RETURNS the new state; it does
        not publish or cache it itself (that happens on the loop thread)."""
        with mock.patch.object(actions.mac, "set_volume"):
            hint = actions.volume_set(level=55)
        self.assertGreater(state._settle_until.get("mac.volume", 0), 0)  # noqa: SLF001
        self.assertEqual(hint, ("mac.volume", {"state": "55",
                                               "attributes": {"level": 55, "muted": False}}))


class Redraw(unittest.IsolatedAsyncioTestCase):
    """A local action must redraw the keys that render its entity.

    Regression: the optimistic cache update used to make the poller compare
    equal, so nothing was ever published and the Mute Mac key stayed stale even
    though the Mac really did mute. Dials hid it by redrawing eagerly on turn.
    """

    async def asyncSetUp(self) -> None:
        self.deck = FakeDeck()
        # a key whose icon depends on mac.volume's `muted` attribute
        self.btn = app.Button(
            entity_id="mac.volume",
            service="mac.volume_mute",
            icon="{{ 'on.png' if state_attr('mac.volume', 'muted') else 'off.png' }}",
        )
        self.cfg = make_config([self.btn])
        self.st: dict[str, Any] = {
            "mac.volume": {"state": "44", "attributes": {"level": 44, "muted": False}},
        }
        state._last.clear()  # noqa: SLF001
        state._settle_until.clear()  # noqa: SLF001
        state._last["mac.volume"] = dict(self.st["mac.volume"])  # noqa: SLF001
        state.bind(self.st, self.cfg, self.deck)
        self._render = mock.patch.object(app.Button, "try_render_icon", _blank_image)
        self._render.start()
        self._native = mock.patch.object(app.PILHelper, "to_native_format", lambda _d, i: b"x" * len(i.tobytes()[:8]))  # noqa: ARG005
        self._native.start()

    async def asyncTearDown(self) -> None:
        self._render.stop()
        self._native.stop()
        state.unbind()

    async def test_mute_press_redraws_the_key(self) -> None:
        with mock.patch.object(actions.mac, "read_volume", return_value=(44, False)), \
             mock.patch.object(actions.mac, "set_muted"):
            await app._handle_key_press(  # noqa: SLF001
                FakeWS(), self.st, self.cfg, self.btn, self.deck, is_long_press=False,
            )
        self.assertTrue(self.deck.key_writes, "key was never redrawn after mute")
        self.assertIs(
            self.st["mac.volume"]["attributes"]["muted"], True,
            "complete_state was not updated, so the icon template still sees the old value",
        )

    async def test_volume_set_publishes_too(self) -> None:
        with mock.patch.object(actions.mac, "set_volume"):
            await actions.dispatch("mac.volume_set", {"level": "77"})
        self.assertEqual(self.st["mac.volume"]["attributes"]["level"], 77)
        self.assertEqual(self.st["mac.volume"]["state"], "77")

    async def test_unbound_session_defers_to_the_poller(self) -> None:
        """No session (press during startup) must not crash, and must not
        leave a cached value that hides the change from the next poll."""
        state.unbind()
        with mock.patch.object(actions.mac, "set_volume"):
            await actions.dispatch("mac.volume_set", {"level": 5})
        self.assertNotIn("mac.volume", state._last)  # noqa: SLF001


class Handlers(unittest.IsolatedAsyncioTestCase):
    async def test_level_is_coerced_and_clamped(self) -> None:
        with mock.patch.object(actions.mac, "set_volume") as sv, \
             mock.patch.object(actions.mac, "read_volume", return_value=(0, False)):
            actions.volume_set(level="42")        # template output is a string
            actions.volume_set(level=150)         # clamp high
            actions.volume_set(level=-5)          # clamp low
            actions.volume_set(level=33, entity_id="mac.volume")  # app-injected key
        self.assertEqual([c.args[0] for c in sv.call_args_list], [42, 100, 0, 33])

    async def test_open_app_passes_the_name_through(self) -> None:
        btn = app.Button(service="mac.open_app", service_data={"app": "1Password"})
        ws = FakeWS()
        with mock.patch.object(actions.mac, "open_app") as open_app:
            await app._handle_key_press(  # noqa: SLF001
                ws, {}, make_config([btn]), btn, FakeDeck(), is_long_press=False,
            )
        open_app.assert_called_once_with("1Password")
        self.assertEqual(ws.sent, [], "mac.open_app leaked to Home Assistant")

    async def test_open_app_without_a_name_is_contained(self) -> None:
        await actions.dispatch("mac.open_app", {})  # must not raise

    async def test_open_app_reports_an_unknown_app(self) -> None:
        """Real subprocess, no mock — a bad name must raise MacError, not hang."""
        with self.assertRaises(mac_mod.MacError):
            mac_mod.open_app("ZZZ-no-such-application-here")

    async def test_unknown_action_is_logged_not_raised(self) -> None:
        await actions.dispatch("mac.nope", {})  # must not raise

    async def test_handler_failure_is_contained(self) -> None:
        with mock.patch.object(actions.mac, "set_volume", side_effect=OSError("boom")):
            await actions.dispatch("mac.volume_set", {"level": 10})  # must not raise

    async def test_caffeinate_self_toggles_like_mute(self) -> None:
        with mock.patch.object(actions.mac, "caffeinate_running", return_value=False), \
             mock.patch.object(actions.mac, "set_caffeinate") as set_caffeinate:
            hint = actions.caffeinate_set()
        set_caffeinate.assert_called_once_with(True)
        self.assertEqual(hint, ("mac.caffeinate", {"state": "on", "attributes": {}}))

    async def test_caffeinate_accepts_an_explicit_value(self) -> None:
        with mock.patch.object(actions.mac, "set_caffeinate") as set_caffeinate:
            hint = actions.caffeinate_set(on="false")
        set_caffeinate.assert_called_once_with(False)
        self.assertEqual(hint, ("mac.caffeinate", {"state": "off", "attributes": {}}))

    async def test_keepawake_goes_through_launchservices(self) -> None:
        """Tier 0 is the whole point: it must drive KeepingYouAwake with
        `open` (LaunchServices), never osascript. An Apple event would need
        Automation approval, which for a LaunchAgent attaches to the
        responsible binary and cannot be granted non-interactively.
        """
        ok = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(mac_mod.subprocess, "run", return_value=ok) as run:
            mac_mod.set_caffeinate(True)
            mac_mod.set_caffeinate(False)
        self.assertEqual(
            [c.args[0] for c in run.call_args_list],
            [
                ["/usr/bin/open", "-g", "keepingyouawake:///activate"],
                ["/usr/bin/open", "-g", "keepingyouawake:///deactivate"],
            ],
        )

    async def test_keepawake_failure_is_reported(self) -> None:
        """e.g. KeepingYouAwake not installed — `open` exits non-zero."""
        bad = subprocess.CompletedProcess([], 1, "", "Unable to find application")
        with mock.patch.object(mac_mod.subprocess, "run", return_value=bad), \
             self.assertRaises(mac_mod.MacError):
            mac_mod.set_caffeinate(True)

    async def test_state_is_scoped_to_keepingyouawake(self) -> None:
        """Regression guard: a bare `pgrep -x caffeinate` also matches an
        UNRELATED caffeinate (one started in a Terminal, or a leftover from an
        older build of this repo). The key would then read "on" while the off
        press — which only talks to KYA — could not turn it off, leaving the
        button visibly stuck.
        """
        seen: list[tuple[str, ...]] = []

        def fake_pgrep(*args: str) -> list[str]:
            seen.append(args)
            return ["4242"] if args == ("-x", "KeepingYouAwake") else []

        with mock.patch.object(mac_mod, "_pgrep", fake_pgrep):
            self.assertFalse(mac_mod.caffeinate_running())
        self.assertIn(
            ("-P", "4242", "-x", "caffeinate"), seen,
            "state was not scoped to KYA's own child processes",
        )

    async def test_state_true_only_when_kya_holds_caffeinate(self) -> None:
        with mock.patch.object(mac_mod, "_pgrep", side_effect=[["4242"], ["4243"]]):
            self.assertTrue(mac_mod.caffeinate_running())
        # KYA not running at all — must not even look for a caffeinate child
        with mock.patch.object(mac_mod, "_pgrep", return_value=[]) as pg:
            self.assertFalse(mac_mod.caffeinate_running())
        self.assertEqual(pg.call_count, 1)


async def _fake_get_states(websocket: Any) -> dict[str, Any]:  # noqa: ARG001
    # Parameter name matters: wrap._check() asserts the real signature, so a
    # stub standing in for it has to match too.
    return {"light.real": {"state": "on", "attributes": {}}}


def _blank_image(self: Any, *a: Any, **k: Any) -> Any:  # noqa: ANN401, ARG001
    from PIL import Image

    return Image.new("RGB", (200, 100), "black")


if __name__ == "__main__":
    unittest.main(verbosity=2)
