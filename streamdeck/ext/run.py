"""Entry point: `python -m ext.run [same args as home-assistant-streamdeck-yaml]`.

Installs the local-action wrappers and then hands off to the upstream `main()`,
so all CLI flags, .env handling, deck detection, signal handlers and reconnect
logic stay exactly as upstream defines them.

Upstream `main()` returns only when the app has stopped driving the deck: its
retry loop gave up, or it hit an exception it does not retry and "broke" out
(after resetting the deck). Both exit 0, and launchd's KeepAlive
(`SuccessfulExit: false`) never restarts a successful exit — so the deck just
sat there dead. Exiting 1 instead hands it to launchd. Ctrl-C and SIGTERM are
unaffected: upstream's signal handler raises SystemExit(0) and never returns
here.
"""
from __future__ import annotations

import sys

import home_assistant_streamdeck_yaml as app

from . import wrap


def main() -> None:
    wrap.install()
    app.main()
    app.console.log("[red]ext: the app stopped on its own; exiting 1 so launchd restarts it[/]")
    sys.exit(1)


if __name__ == "__main__":
    main()
