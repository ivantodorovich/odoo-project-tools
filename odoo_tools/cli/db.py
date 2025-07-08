# Copyright 2023 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import getpass
import os
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Callable

import click
import psycopg2

from ..utils.db import ensure_db_container_up, execute_db_request, get_db_list
from ..utils.os_exec import run
from ..utils.path import cd, make_dir
from ..utils.proj import get_project_manifest_key


def handle_exceptions() -> Callable:
    """Decorator to handle exceptions and print a nice error message."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                raise click.ClickException(f"Failed to {func.__name__}: {e}") from e

        return wrapper

    return decorator


def get_default_parameters():
    """Get default platform and customer parameters from project manifest."""
    ctx_platform = get_project_manifest_key("country")
    if not ctx_platform:
        raise click.ClickException("Please specify the platform")

    project_name = get_project_manifest_key("project_name")
    ctx_customer = "-".join(project_name.split("_")[:-1])
    return ctx_platform, ctx_customer


def expand_path(path):
    """Expand user home directory in path."""
    if path.startswith("~"):
        path = os.path.expanduser(path)
    return path


def _download_from_azure(platform, customer, env, dump_name):
    """Download one dump from Azure with celebrimbor_cli."""
    run(
        f"celebrimbor_cli -p {platform} download -c {customer} -e {env} --name {dump_name}"
    )


def _get_list_of_dumps(platform, customer, env):
    """Retrieve list of dumps from Azure with celebrimbor_cli."""
    result = run(f"celebrimbor_cli -p {platform} list -c {customer} -e {env} -r")
    result_data = eval(result)
    return [fname["name"] for fname in result_data or []]


@click.group()
def cli():
    """Database management commands."""
    pass


@cli.command()
@handle_exceptions()
def list():
    """List all databases in the container."""
    db_list = get_db_list()
    if not db_list:
        click.echo("No databases found")
        return

    click.echo("Databases:")
    for db_name in sorted(db_list):
        click.echo(f"  {db_name}")


@cli.command("list-versions")
@handle_exceptions()
def list_versions():
    """Print a table of DBs with Marabunta version and install date."""
    res = {}
    sql = """
        SELECT date_done, number
        FROM marabunta_version
        ORDER BY date_done DESC
        LIMIT 1;
    """

    db_list = get_db_list()
    for db_name in db_list:
        try:
            version_fetch = execute_db_request(db_name, sql)
            version_tuple = version_fetch[0] if version_fetch else (None, "unknown")
        except psycopg2.ProgrammingError:
            # Error expected when marabunta_version table does not exist
            version_tuple = (None, "unknown")
        res[db_name] = version_tuple

    if not res:
        click.echo("No databases found")
        return

    # Calculate column sizes
    # TODO: Use rich for this
    size1 = max([len(x) for x in res.keys()]) + 1
    size2 = max([len(str(x[1])) for x in res.values()]) + 1
    size3 = 12  # len("2018-01-01") + margin

    # Print header
    cols = (("DB Name", size1), ("Version", size2), ("Install date", size3))
    thead = ""
    line_width = 4  # spaces
    for col_name, col_size in cols:
        thead += "{:<{size}}".format(col_name, size=col_size + 1)
        line_width += col_size

    click.echo(thead)
    click.echo("=" * line_width)

    # Print data
    for db_name, version in sorted(
        res.items(), key=lambda x: x[1][0] or datetime.min, reverse=True
    ):
        if version[0]:
            time_str = version[0].strftime("%Y-%m-%d")
        else:
            time_str = "unknown"
        click.echo(
            "{:<{size1}} {:<{size2}} {:<12}".format(
                db_name, str(version[1]), time_str, size1=size1, size2=size2
            )
        )


@cli.command("restore-dump")
@click.argument("dump_path", type=click.Path(exists=True, readable=True))
@click.option(
    "--db-name",
    help="Name of the database to restore to. If not specified, uses the dump filename.",
)
@click.option(
    "--hide-traceback/--show-traceback",
    default=True,
    help="Hide traceback information during restore.",
)
def restore_dump(dump_path, db_name, hide_traceback):
    """Restore a PostgreSQL dump to a database."""
    try:
        if not db_name:
            # Use filename without extension as db name
            db_name = Path(dump_path).stem

        # Create database
        run(f"docker compose run --rm odoo createdb -O odoo {db_name}")
        click.echo(f"Restoring {dump_path} to {db_name}")

        # Restore dump
        expanded_path = expand_path(dump_path)
        run(
            f"docker compose run --rm odoo pg_restore -O -d {db_name} < {expanded_path}"
        )

        click.echo(f"Dump successfully restored to {db_name}")

        if db_name != "odoodb":
            click.echo("You can run Odoo on this DB:")
            click.echo(
                f"docker compose run --rm -e DB_NAME={db_name} "
                "-p 8069:8069 odoo odoo --workers=0"
            )
    except Exception as e:
        raise click.ClickException(f"Failed to restore dump: {e}") from e


@cli.command("download-restore")
@click.option("--platform", help="Platform to run the command on")
@click.option("--customer", help="Customer name")
@click.option("--env", default="int", help="Environment (prod, int, labs.<lab-name>)")
@click.option("--dump-name", help="Specific dump name to download")
@click.option(
    "--dumpdir", default=".", type=click.Path(), help="Directory to store dumps"
)
@click.option("--restore-db", help="Name of the database to restore to")
def download_restore(platform, customer, env, dump_name, dumpdir, restore_db):
    """Download a dump from Azure and restore it."""
    try:
        ctx_platform, ctx_customer = get_default_parameters()
        p_platform = platform or ctx_platform
        p_customer = customer or ctx_customer

        # Get dump name if not specified
        if not dump_name:
            dumps = _get_list_of_dumps(p_platform, p_customer, env)
            if not dumps:
                raise click.ClickException(
                    f"No dumps found for {p_customer} on {p_platform} {env}"
                )
            dump_name = dumps[-1]  # Get the latest

        # Download dump
        make_dir(dumpdir)
        gpg_fname = os.path.basename(dump_name)
        fname = os.path.splitext(gpg_fname)[0]

        with cd(dumpdir):
            if not os.path.isfile(fname):
                click.echo(f"Downloading dump: {dump_name}")
                click.echo(f"From: {p_platform} {env} of {p_customer}")
                click.echo(f"To: {os.getcwd()}")
                _download_from_azure(p_platform, p_customer, env, dump_name)
            else:
                click.echo(f"File {fname} already exists, skipping download.")

        dump_path = os.path.join(dumpdir, fname)

        # Restore dump
        if not restore_db:
            restore_db = Path(dump_path).stem

        # Create database
        run(f"docker compose run --rm odoo createdb -O odoo {restore_db}")
        click.echo(f"Restoring {dump_path} to {restore_db}")

        # Restore
        expanded_path = expand_path(dump_path)
        run(
            f"docker compose run --rm odoo pg_restore -O -d {restore_db} < {expanded_path}"
        )

        click.echo(f"Dump successfully restored to {restore_db}")

    except Exception as e:
        raise click.ClickException(f"Failed to download and restore: {e}") from e


@cli.command()
@click.option("--db-name", default="odoodb", help="Name of the database to dump")
@click.option("--path", default=".", type=click.Path(), help="Path to store the dump")
def dump(db_name, path):
    """Create a PostgreSQL dump of the specified database."""
    try:
        path = expand_path(path)

        with ensure_db_container_up() as db_port:
            username = getpass.getuser()
            project_name = get_project_manifest_key("project_name")
            dump_name = f"{username}_{project_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pg"
            dump_file_path = f"{path}/{dump_name}"

            run(
                f"pg_dump -h localhost -p {db_port} --format=c -U odoo --file {dump_file_path} {db_name}"
            )
            click.echo(f"Dump successfully generated at {dump_file_path}")
            return dump_file_path

    except Exception as e:
        raise click.ClickException(f"Failed to create dump: {e}") from e


@cli.command("dump-and-share")
@click.option("--platform", help="Platform to run the command on")
@click.option("--customer", help="Customer name")
@click.option("--env", default="int", help="Environment (prod, int, labs.<lab-name>)")
@click.option("--db-name", default="odoodb", help="Name of the database to dump")
@click.option("--tmp-path", default="/tmp", help="Temporary path to store the dump")
@click.option(
    "--keep-local-dump/--remove-local-dump",
    default=False,
    help="Keep the generated dumps locally",
)
def dump_and_share(platform, customer, env, db_name, tmp_path, keep_local_dump):
    """Create a dump and share it on Azure."""
    try:
        ctx_platform, ctx_customer = get_default_parameters()
        p_platform = platform or ctx_platform
        p_customer = customer or ctx_customer
        tmp_path = expand_path(tmp_path)

        # Create local dump
        with ensure_db_container_up() as db_port:
            username = getpass.getuser()
            project_name = get_project_manifest_key("project_name")
            dump_name = f"{username}_{project_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pg"
            dump_file_path = f"{tmp_path}/{dump_name}"

            run(
                f"pg_dump -h localhost -p {db_port} --format=c -U odoo --file {dump_file_path} {db_name}"
            )
            click.echo(f"Dump successfully generated at {dump_file_path}")

        # Upload to Azure
        run(
            f"celebrimbor_cli -p {p_platform} dump -c {p_customer} -e {env} -i {dump_file_path}"
        )
        click.echo(f"Dump uploaded for {p_customer} on {p_platform} {env}")

        # Clean up if requested
        if not keep_local_dump:
            os.remove(dump_file_path)
            click.echo("Local dump file removed")

    except Exception as e:
        raise click.ClickException(f"Failed to dump and share: {e}") from e


if __name__ == "__main__":
    cli()
