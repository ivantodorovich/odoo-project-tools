# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from __future__ import annotations

from click.exceptions import Exit as _Exit


class PathNotFound(IOError):
    pass


class ProjectRootFolderNotFound(IOError):
    pass


class ProjectConfigException(Exception):
    pass


class Exit(_Exit):
    def __init__(self, msg: str, exit_code: int = 1) -> None:
        super().__init__(exit_code)
        self.message = msg
        print(self.message)


# TODO: manage exceptions globally and homogeneously.
# See https://stackoverflow.com/questions/45875930/is-there-a-way-to-handle-exceptions-automatically-with-python-click
