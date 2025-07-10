# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from __future__ import annotations

import fileinput
import operator
import os
from pathlib import Path
from typing import Any, Callable

import requirements

from ..config import get_conf_key
from . import ui
from .gh import parse_github_url
from .path import root_path
from .pypi import pkg_name_to_odoo_name

# https://requirements-parser.readthedocs.io/en/latest/


def get_project_req() -> Path:
    return root_path() / "requirements.txt"


def get_project_dev_req() -> Path:
    return root_path() / "dev_requirements.txt"


def get_requirements(req_filepath: Path | None = None) -> dict[str, Any]:
    req_filepath = req_filepath or get_project_req()
    res = {}
    with open(req_filepath) as fd:
        for req in requirements.parse(fd):
            res[req.name] = req
    return res


def get_addon_requirement(addon: str, req_filepath: Path | None = None) -> Any | None:
    req_filepath = req_filepath or get_project_req()
    with open(req_filepath) as fd:
        for req in requirements.parse(fd):
            if req.name in (addon, pkg_name_to_odoo_name(addon)):
                return req
    return None


def make_requirement_line(pkg_name: str, version: str | None = None) -> str:
    return pkg_name + (f" == {version}" if version else "")


def make_requirement_line_for_pr(pkg_name: str, pr: str, use_wool: bool = False) -> str:
    mod_name = pkg_name_to_odoo_name(pkg_name)
    parts = parse_github_url(pr)
    uri = "git+https://github.com/{upstream}/{repo_name}@refs/{entity_type}/{entity_id}/head".format(
        **parts
    )
    subdirectory = modname_to_installation_subdirectory(mod_name, use_wool)
    return f"{pkg_name} @ {uri}#subdirectory={subdirectory}"


def modname_to_installation_subdirectory(mod_name: str, use_wool: bool) -> str:
    if use_wool:
        subdirectory = f"{mod_name}"
    else:
        subdirectory = f"setup/{mod_name}"
    return subdirectory


def make_requirement_line_for_proj_fork(
    pkg_name: str, repo_name: str, branch: str, upstream: str | None = None, use_wool: bool = False
) -> str:
    upstream = upstream or get_conf_key("company_git_remote")
    mod_name = pkg_name_to_odoo_name(pkg_name)
    parts = {
        "upstream": upstream,
        "branch": branch,
        "repo_name": repo_name,
    }
    uri = "git+https://github.com/{upstream}/{repo_name}@{branch}".format(**parts)
    subdirectory = modname_to_installation_subdirectory(mod_name, use_wool)
    return f"{pkg_name} @ {uri}#subdirectory={subdirectory}"


def make_requirement_line_for_editable(
    pkg_name: str, pr: str | None = None, repo_name: str | None = None, dev_src: str | None = None, use_wool: bool = False
) -> str:
    assert pr or repo_name
    if pr:
        parts = parse_github_url(pr)
        repo_name = parts["repo_name"]
    dev_src = dev_src or get_conf_key("ext_src_rel_path")
    mod_name = pkg_name_to_odoo_name(pkg_name)
    subdirectory = modname_to_installation_subdirectory(mod_name, use_wool)
    return f"-e {dev_src}/{repo_name}/{subdirectory}"


def add_requirement(
    pkg_name: str, version: str | None = None, req_filepath: Path | None = None, pr: str | None = None, editable: bool = False, use_wool: bool | None = None
) -> None:
    req_filepath = req_filepath or get_project_req()
    if use_wool is None:
        # assume a project on Odoo 17 is using wool
        use_wool = version is None or version >= "17"
    if pr:
        handler = make_requirement_line_for_pr
        if editable:
            handler = make_requirement_line_for_editable
        line = handler(pkg_name, pr, use_wool=use_wool)
    else:
        line = make_requirement_line(pkg_name, version=version)
    sep = "\n" if os.path.exists(req_filepath) else ""
    with open(req_filepath, "a") as fd:
        fd.write(sep + line)


def replace_requirement(
    pkg_name: str, version: str | None = None, req_filepath: Path | None = None, pr: str | None = None, editable: bool = False, use_wool: bool | None = None
) -> None:
    req_filepath = req_filepath or get_project_req()
    if use_wool is None:
        # assume a project on Odoo 17 is using wool
        use_wool = version is not None and version >= "17"
    if pr:
        handler = make_requirement_line_for_pr
        if editable:
            handler = make_requirement_line_for_editable
        replacement_line = handler(pkg_name, pr, use_wool=use_wool)
    else:
        replacement_line = make_requirement_line(
            pkg_name,
            version=version,
        )
    for line in fileinput.input(req_filepath, inplace=True):
        # `print` replaces line inside fileinput ctx manager
        # TODO: add tests for all the forms of requirements
        if pkg_name in line or pkg_name_to_odoo_name(pkg_name) in line:
            line = replacement_line
        # NOTE: this will add an empty line at the end w/ `\n`
        ui.echo(line)


OP: dict[str, Callable[[Any, Any], bool]] = {
    "==": operator.eq,
    "<=": operator.le,
    ">=": operator.ge,
    ">": operator.gt,
    "<": operator.lt,
}


def allowed_version(req: Any, check_version: str) -> bool:
    for _op, version in req.specs:
        op = OP[_op]
        if not op(check_version, version):
            return False
    return True
