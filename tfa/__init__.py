import os
import json
import sys
from pathlib import Path
import click
import pyotp
import qrcode


def get_keyfile():
    keyfile = os.environ.get("TFA_STORAGE")
    if not keyfile:
        click.echo("Please define a TFA_STORAGE an envionment variable.")
        exit()

    return Path(keyfile)


def get_storage():
    keyfile = os.environ.get("TFA_STORAGE")
    if not keyfile:
        click.echo("Please define a TFA_STORAGE an envionment variable.")
        exit()

    keypath = Path(keyfile)

    if not keypath.exists():
        return {}

    return json.load(keypath.open("r"))


def get_account(account_name):
    accounts = get_storage()
    try:
        return accounts[account_name]
    except KeyError:
        click.echo(
            f"Account {account_name!r} not found. Available accounts:",
            err=True,
        )
        for account in accounts:
            print(account)
        sys.exit(1)


def save_accounts(accounts):
    json.dump(accounts, get_keyfile().open("w"))


@click.group()
def cli():
    pass


@cli.command(help="Show a TOTP code for a given account.")
@click.argument("account")
def code(account):
    account = get_account(account)
    totp = pyotp.TOTP(account["key"])
    print(f"{account['issuer']}: {totp.now()}")


@cli.group(help="Manage accounts.")
def account():
    pass


@account.command(help="Add a new account.", name="add")
@click.argument("account_name")
@click.argument("secret_key")
@click.option(
    "--issuer",
)
def add_account(account_name, secret_key, issuer=None):
    issuer = issuer or account_name
    accounts = get_storage()
    accounts[account_name] = {"issuer": issuer, "key": secret_key}
    save_accounts(accounts)


@account.command(help="Remove an account.", name="remove")
@click.argument("name")
def remove_account(name):
    accounts = get_storage()
    accounts.pop(name, None)
    save_accounts(accounts)


@account.command(help="List all accounts.", name="list")
def list_accounts():
    for name in get_storage():
        print(name)


@cli.command(help="Display a QR code for an account.")
@click.argument("account")
def qr(account):
    account = get_account(account)

    totp = pyotp.TOTP(account["key"])
    url = totp.provisioning_uri(issuer_name=account["issuer"])
    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.print_ascii()


if __name__ == "__main__":
    cli()
