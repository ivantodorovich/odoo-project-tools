# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from __future__ import annotations

import os
from contextlib import contextmanager
from os import PathLike
from pathlib import Path, PosixPath
from typing import Iterator, Union

from ..exceptions import ProjectRootFolderNotFound
from . import ui


def get_root_marker() -> str:
    return ".cookiecutter.context.yml"


# TODO: consider using `git rev-parse --show-superproject-working-tree / --show-toplevel`
# to find out the root of the project w/o relying on marker files.


def root_path(marker_file: str = get_root_marker(), raise_if_missing: bool = True) -> Path:
    """Look for the root directory by looking for a marker file."""
    cwd = Path.cwd()
    for potential_root_path in [cwd, *cwd.parents]:
        marker_file_path = potential_root_path / marker_file
        if marker_file_path.exists():
            return potential_root_path
    if raise_if_missing:
        raise ProjectRootFolderNotFound(
            f"Could not find a '{marker_file}' file in {cwd} or any parent directories."
        )
    return cwd


# TODO: add test
def build_path(path: Union[str, PathLike[str]], from_root: bool = True, from_file: str | None = None) -> Path:
    """Build a ``Path`` object relative to the root directory by default.

    :param path: string or pathlike object to process
    :param from_root: build relative to the detected project root directory
    :param from_file: build relative to the provided file
    """
    path = Path(path)
    if from_file:
        return Path(from_file).parent / path
    elif from_root and not path.is_absolute():
        return root_path() / path
    return path


@contextmanager
def cd(path: Union[str, PathLike[str]]) -> Iterator[None]:
    """Context manager that temporary changes current directory.

    Usage::

        with cd("some/path"):
            # do something
    """
    prev = os.getcwd()
    os.chdir(build_path(path))
    try:
        yield
    finally:
        os.chdir(prev)


def make_dir(path_dir: Union[str, PathLike[str]]) -> None:
    try:
        os.makedirs(path_dir)
    except OSError:
        if not os.path.isdir(path_dir):
            msg = f"Directory does not exist and could not be created: {path_dir}"
            ui.exit_msg(msg)
        else:
            pass  # directory already exists, nothing to do in this case
