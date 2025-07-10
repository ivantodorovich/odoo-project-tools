# Copyright 2025 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from __future__ import annotations

from pathlib import Path

from . import docker_compose, os_exec, ui


def create_db_from_db_dump(
    db_name: str,
    db_dump: str,
    template_db_name: str | None = None,
) -> None:
    """Restores a DB dump, optionally creates a DB template

    :param str db_name: name of the DB to create
    :param str db_dump: filename of the DB dump to restore
    :param str template_db_name: if set, a new template DB of the given name is created
    """
    if template_db_name:
        _handle_database_template(template_db_name, db_dump)
        _restore_database_from_template(db_name, template_db_name)
    else:
        _load_database(db_name, db_dump)


def create_db_from_db_template(db_name: str, db_template: str) -> None:
    """Creates a new DB from the given template

    :param str db_name: name of the DB to create
    :param str db_template: the name of the template DB to use
    """
    _restore_database_from_template(db_name, db_template)


def create_db_from_local_files(
    db_name: str,
    template_db_name: str | None = None,
) -> None:
    """Checks current directory for ``.pg`` files and tries to restore one of them

    :param str db_name: name of the DB to create
    :param str template_db_name: if set, a new template DB of the given name is created
    """
    if dumps := [d.name for d in Path(".").absolute().glob("*.pg") if d.is_file()]:
        dumps.sort()  # Sort alphabetically to make it easier to read for users
        choices: dict[int, str] = dict(enumerate(dumps, start=1))
        ui.echo(
            "Found the following DB dumps:\n"
            + "\n".join(f"{i} - {n}" for i, n in choices.items())
        )
        key = ui.ask_question("Enter the number of the DB dump to restore", type=int)
        # Ensure key is an integer for dict lookup
        try:
            key_int = int(key) if isinstance(key, str) else key
            if db_dump := choices.get(key_int):
                create_db_from_db_dump(db_name, db_dump, template_db_name)
            else:
                ui.exit_msg(
                    f"Invalid selection: {key} not found in {', '.join(map(str, choices))}"
                )
        except (ValueError, TypeError):
            ui.exit_msg(f"Invalid selection: {key} is not a valid number")
    else:
        ui.exit_msg("No database dump found")


def _handle_database_template(template_db_name: str, db_dump: str) -> None:
    """Creates or updates a database template."""
    if _database_exists(template_db_name):
        if ui.ask_confirmation(f"Template database {template_db_name} already exists. Overwrite?"):
            _drop_database(template_db_name)
        else:
            return
    _load_database(template_db_name, db_dump)


def _restore_database_from_template(db_name: str, template_db_name: str) -> None:
    """Creates a new database from a template."""
    if _database_exists(db_name):
        if ui.ask_confirmation(f"Database {db_name} already exists. Overwrite?"):
            _drop_database(db_name)
        else:
            return
    
    cmd = [
        "docker", "compose", "exec", "-T", "db",
        "createdb", "-T", template_db_name, db_name
    ]
    os_exec.run(cmd, check=True)
    ui.echo(f"Database {db_name} created from template {template_db_name}")


def _load_database(db_name: str, db_dump: str) -> None:
    """Loads a database from a dump file."""
    dump_path = Path(db_dump)
    if not dump_path.exists():
        ui.exit_msg(f"Database dump file not found: {db_dump}")
    
    if _database_exists(db_name):
        if ui.ask_confirmation(f"Database {db_name} already exists. Overwrite?"):
            _drop_database(db_name)
        else:
            return
    
    # Create the database
    create_cmd = [
        "docker", "compose", "exec", "-T", "db",
        "createdb", db_name
    ]
    os_exec.run(create_cmd, check=True)
    
    # Restore the dump
    restore_cmd = [
        "docker", "compose", "exec", "-T", "db",
        "pg_restore", "-d", db_name
    ]
    
    with open(dump_path, 'rb') as dump_file:
        import subprocess
        result = subprocess.run(restore_cmd, stdin=dump_file, check=True)
    
    ui.echo(f"Database {db_name} loaded from {db_dump}")


def _database_exists(db_name: str) -> bool:
    """Check if a database exists."""
    cmd = [
        "docker", "compose", "exec", "-T", "db",
        "psql", "-lqt"
    ]
    result = os_exec.run(cmd)
    return db_name in result


def _drop_database(db_name: str) -> None:
    """Drop a database."""
    cmd = [
        "docker", "compose", "exec", "-T", "db",
        "dropdb", db_name
    ]
    os_exec.run(cmd, check=True)
    ui.echo(f"Database {db_name} dropped")
