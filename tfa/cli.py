import sys

import click
import pyotp
import qrcode
import binascii

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
    click.echo(f"{account['issuer']}: {totp.now()}")


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
        click.echo(f"{account_name}: { initial_code }")
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
