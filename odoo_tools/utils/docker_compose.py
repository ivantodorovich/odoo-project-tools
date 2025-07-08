# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
"""
Helper functions to get docker compose commands to run, handling the different
command line options found in different versions of docker compose.
"""

from __future__ import annotations

import subprocess
from typing import Any

from . import os_exec


def get_version() -> list[int]:
    version = os_exec.run("docker compose version --short")
    return [int(x) for x in version.split(".") if x.isdigit()]


def get_base_cmd() -> list[str]:
    """Get the base docker compose command."""
    version = get_version()
    if version[0] >= 2:
        return ["docker", "compose"]
    else:
        return ["docker-compose"]


def build_cmd(service: str | None = None, **kwargs: Any) -> list[str]:
    """Build a docker compose command.
    
    :param service: Optional service name to target
    :param kwargs: Additional docker compose options
    """
    cmd = get_base_cmd()
    
    # Add any additional options
    for key, value in kwargs.items():
        if value is True:
            cmd.append(f"--{key.replace('_', '-')}")
        elif value and value is not False:
            cmd.extend([f"--{key.replace('_', '-')}", str(value)])
    
    if service:
        cmd.append(service)
    
    return cmd


def run_cmd(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    """Run a docker compose command.
    
    :param cmd: The command to run
    :param kwargs: Additional subprocess options
    """
    return subprocess.run(cmd, **kwargs)


def up(override: str | None = None) -> list[str]:
    command = ["docker", "compose", "up"]
    if override:
        command.extend(["-f", override])
    return command


def run(
    service: str,
    command_str: str = "",
    rm: bool = True,
    user: str | None = None,
    name: str | None = None,
    override: str | None = None,
) -> list[str]:
    """
    Return the docker compose run command as a list

    :param str service: Service name to run
    :param str command_str: Command to run inside the service
    :param bool rm: Add --rm flag
    :param str user: User override
    :param str name: Container name
    :param str override: Override file path
    """
    command = []
    if override:
        command.extend(["-f", override])
    command.extend(["docker", "compose", "run"])
    if rm:
        command.append("--rm")
    if user:
        command.extend(["-u", user])
    if name:
        command.extend(["--name", name])
    command.append(service)
    if command_str:
        command.extend(command_str.split())
    return command


def pull(service: str | None = None) -> list[str]:
    command = ["docker", "compose", "pull"]
    if service:
        command.append(service)
    return command


def build(service: str | None = None) -> list[str]:
    command = ["docker", "compose", "build"]
    if service:
        command.append(service)
    return command


def down() -> list[str]:
    return ["docker", "compose", "down"]


def drop_db(db_name: str) -> list[str]:
    return run("db", f"dropdb {db_name}", rm=True)


def create_db(db_name: str) -> list[str]:
    return run("db", f"createdb {db_name}", rm=True)


def restore_db(db_name: str, backup_file: str) -> list[str]:
    return run("db", f"pg_restore -d {db_name} < {backup_file}", rm=True)


def restore_db_from_template(db_name: str, template_name: str) -> list[str]:
    return run("db", f"createdb -T {template_name} {db_name}", rm=True)


def run_restore_db(db_name: str, backup_file: str) -> None:
    cmd = restore_db(db_name, backup_file)
    os_exec.run(cmd)
