"""Entry point: `python -m ext.run [same args as home-assistant-streamdeck-yaml]`.

Installs the local-action wrappers and then hands off to the upstream `main()`,
so all CLI flags, .env handling, deck detection, signal handlers and reconnect
logic stay exactly as upstream defines them.
"""
from __future__ import annotations

import home_assistant_streamdeck_yaml as app

from . import wrap


def main() -> None:
    wrap.install()
    app.main()


if __name__ == "__main__":
    main()
