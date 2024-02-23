import json
import sys
import click
import pyotp
import qrcode


TFA_STORAGE = "/home/akelly/.tfa"
ACCOUNTS = json.load(open(TFA_STORAGE, "r"))


def save_accounts(accounts):
    json.dump(ACCOUNTS, open(TFA_STORAGE, "w"))


@click.group()
def cli():
    pass


@cli.command(help="Show a TOTP code for a given account.")
@click.argument("account")
def code(account):
    try:
        account = ACCOUNTS[account]
    except KeyError:
        click.echo(
            f"Account {account!r} not found in: {list(ACCOUNTS.keys())}",
            err=True,
        )
        sys.exit(1)

    totp = pyotp.TOTP(account["key"])
    print(f"{account['issuer']}: {totp.now()}")


@cli.group(help="Manage accounts.")
def account():
    pass


@account.command(help="Add a new account.", name="add")
@click.argument("name")
@click.argument("issuer")
@click.argument("key")
def add_account(name, issuer, key):
    ACCOUNTS[name] = {"issuer": issuer, "key": key}
    save_accounts(ACCOUNTS)


@account.command(help="Remove an account.", name="remove")
@click.argument("name")
def remove_account(name):
    ACCOUNTS.pop(name, None)
    save_accounts(ACCOUNTS)


@account.command(help="List all accounts.", name="list")
def list_accounts():
    for name in ACCOUNTS:
        print(name)


@cli.command(help="Display a QR code for an account.")
@click.argument("account")
def qr(account):
    account = ACCOUNTS[account]

    totp = pyotp.TOTP(account["key"])
    url = totp.provisioning_uri(issuer_name=account["issuer"])
    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.print_ascii()


if __name__ == "__main__":
    cli()
