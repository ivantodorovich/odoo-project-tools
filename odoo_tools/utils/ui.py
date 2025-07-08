# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from __future__ import annotations

from typing import Any

import click

from ..exceptions import Exit


def exit_msg(msg: str) -> None:
    raise Exit(msg)


def ask_confirmation(message: str) -> bool:
    """Gently ask user's opinion."""
    r = input(message + " (y/N) ")
    return r in ("y", "Y", "yes")


def ask_or_abort(message: str) -> None:
    """Fail (abort) immediately if user disagrees."""
    if not ask_confirmation(message):
        exit_msg("Aborted")


def echo(msg: str, *pa: Any, **kw: Any) -> None:
    cmd = click.echo
    if kw.get("fg"):
        cmd = click.secho
    cmd(msg, *pa, **kw)


def ask_question(message: str, **prompt_kwargs: Any) -> Any:
    """Ask a question and return the answer

    Wrapper around ``click.prompt()``
    """
    return click.prompt(message, **prompt_kwargs)
