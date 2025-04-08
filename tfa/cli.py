import binascii
import click
import json
import pyotp
import qrcode
import sys

from pathlib import Path

from .storage import AccountStorage
from importlib.metadata import version

try:
    __version__ = version("tfa")
except ImportError:
    __version__ = "unknown"


def complete_account_name(ctx, param, incomplete):
    return [k for k in AccountStorage() if k.startswith(incomplete)]


@click.group()
@click.version_option(version=__version__)
def cli():
    pass


@cli.command(help="Show a TOTP code for a given account.")
@click.argument("account_name", shell_complete=complete_account_name)
def code(account_name):
    storage = AccountStorage()
    try:
        account = storage[account_name]
    except KeyError:
        click.echo(f"Account {account_name!r} does not exist.")
        sys.exit(1)
    totp = pyotp.TOTP(account["key"])
    click.echo(f"{totp.now()}")


@cli.command(help="Add a new account.", name="add")
@click.argument("account_name")
@click.argument("secret_key")
@click.option(
    "--issuer",
)
@click.option("--force", "-f", is_flag=True)
def add_account(account_name, secret_key, issuer=None, force=False):
    issuer = issuer or account_name
    accounts = AccountStorage()
    if issuer in accounts and not force:
        click.echo(f"Account {issuer!r} already exists. Use --force to overwrite.")
        sys.exit(1)
    try:
        initial_code = pyotp.TOTP(secret_key).now()
        click.echo(f"{ initial_code }")
    except binascii.Error as error:
        click.echo(f"Invalid secret key: {error}")
        sys.exit(1)

    accounts[account_name] = {"issuer": issuer, "key": secret_key}


@cli.command(help="Remove an account.", name="remove")
@click.argument("account_name", shell_complete=complete_account_name)
def remove_account(account_name):
    accounts = AccountStorage()
    try:
        del accounts[account_name]
    except KeyError:
        click.echo(f"Account {account_name!r} does not exist.")
        sys.exit(1)


@cli.command(help="List all accounts.", name="list")
def list_accounts():
    for name in AccountStorage():
        click.echo(name)


@cli.command(help="Display a QR code for an account.")
@click.argument("account_name", shell_complete=complete_account_name)
def qr(account_name):
    storage = AccountStorage()
    try:
        account = storage[account_name]
    except KeyError:
        click.echo(f"Account {account_name!r} does not exist.")
        sys.exit(1)

    totp = pyotp.TOTP(account["key"])
    url = totp.provisioning_uri(issuer_name=account["issuer"])
    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.print_ascii()


@cli.command(help="Import accounts from a JSON file.", name="import")
@click.argument(
    "json_file", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
@click.option("--force", "-f", is_flag=True, help="Overwrite existing accounts")
def import_accounts(json_file, force):
    """Import accounts from a JSON file into the TFA database."""
    try:
        with json_file.open("r") as f:
            json_accounts = json.load(f)

        storage = AccountStorage()

        imported = 0
        skipped = 0

        for name, details in json_accounts.items():
            if name in storage and not force:
                click.echo(f"Skipping existing account: {name}")
                skipped += 1
                continue

            # Validate the account data
            if not isinstance(details, dict) or "key" not in details:
                click.echo(f"Skipping invalid account data for: {name}")
                skipped += 1
                continue

            if "issuer" not in details:
                details["issuer"] = name

            try:
                pyotp.TOTP(details["key"]).now()
            except binascii.Error as e:
                click.echo(f"Skipping account with invalid key: {name} ({e})")
                skipped += 1
                continue

            storage[name] = details
            imported += 1

        click.echo(f"Import complete: {imported} accounts imported, {skipped} skipped.")

    except json.JSONDecodeError:
        click.echo(f"Error: {json_file} is not a valid JSON file.", err=True)
        sys.exit(1)
    except PermissionError:
        click.echo(f"Error: Permission denied when reading {json_file}", err=True)
        sys.exit(1)
    except FileNotFoundError:
        click.echo(f"Error: File {json_file} not found", err=True)
        sys.exit(1)
    except IOError as e:
        click.echo(f"I/O error when reading {json_file}: {e}", err=True)
        sys.exit(1)


@cli.command(help="Export accounts to a JSON file or stdout.", name="export")
@click.argument(
    "json_file", type=click.Path(dir_okay=False, path_type=Path), required=False
)
@click.option("--force", "-f", is_flag=True, help="Overwrite existing file")
def export_accounts(json_file, force):
    """Export accounts from the TFA database to a JSON file or stdout."""
    storage = AccountStorage()
    accounts = {}

    for name in storage:
        accounts[name] = storage[name]

    if not accounts:
        click.echo("No accounts to export.")
        return

    if not json_file:
        click.echo(json.dumps(accounts, indent=2))
        return

    if json_file.exists() and not force:
        click.echo(
            f"File {json_file} already exists. Use --force to overwrite.", err=True
        )
        sys.exit(1)

    try:
        with json_file.open("w") as f:
            json.dump(accounts, f, indent=2)

        click.echo(f"Successfully exported {len(accounts)} accounts to {json_file}")

    except PermissionError:
        click.echo(f"Error: Permission denied when writing to {json_file}", err=True)
        sys.exit(1)
    except IOError as e:
        click.echo(f"I/O error when writing to {json_file}: {e}", err=True)
        sys.exit(1)


@cli.command(help="Show instructions for enabling shell completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]), default="bash")
def completion(shell):
    """Show instructions for enabling shell completion for tfa."""
    click.echo(f"# To enable {shell} completion for tfa, run the following commands:")

    if shell == "bash":
        click.echo("# Add completion script:")
        click.echo("mkdir -p ~/.local/share/bash-completion/completions/")
        click.echo(
            "_TFA_COMPLETE=bash_source tfa > ~/.local/share/bash-completion/completions/tfa"
        )
        click.echo("")
        click.echo("# Then restart your shell or source the file:")
        click.echo(". ~/.local/share/bash-completion/completions/tfa")
    elif shell == "zsh":
        click.echo("# Add completion script:")
        click.echo("mkdir -p ~/.zfunc")
        click.echo("_TFA_COMPLETE=zsh_source tfa > ~/.zfunc/_tfa")
        click.echo("")
        click.echo("# Add to your ~/.zshrc if not already there:")
        click.echo("fpath+=~/.zfunc")
        click.echo("autoload -Uz compinit && compinit")
    elif shell == "fish":
        click.echo("# Add completion script:")
        click.echo("mkdir -p ~/.config/fish/completions")
        click.echo(
            "_TFA_COMPLETE=fish_source tfa > ~/.config/fish/completions/tfa.fish"
        )
