import sys

import click
import pyotp
import qrcode
import binascii

from .storage import AccountStorage


@click.group()
def cli():
    pass


@cli.command(help="Show a TOTP code for a given account.")
@click.argument("account_name")
def code(account_name):
    storage = AccountStorage()
    try:
        account = storage[account_name]
    except KeyError:
        click.echo(f"Account {account_name!r} does not exist.")
        sys.exit(1)
    totp = pyotp.TOTP(account["key"])
    click.echo(f"{account['issuer']}: {totp.now()}")


@cli.group(help="Manage accounts.")
def account():
    pass


@account.command(help="Add a new account.", name="add")
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


@account.command(help="Remove an account.", name="remove")
@click.argument("account_name")
def remove_account(account_name):
    accounts = AccountStorage()
    try:
        del accounts[account_name]
    except KeyError:
        click.echo(f"Account {account_name!r} does not exist.")
        sys.exit(1)


@account.command(help="List all accounts.", name="list")
def list_accounts():
    for name in AccountStorage():
        click.echo(name)


@cli.command(help="Display a QR code for an account.")
@click.argument("account_name")
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
