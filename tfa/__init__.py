import click
import pyotp
import qrcode

from . import storage


@click.group()
def cli():
    pass


@cli.command(help="Show a TOTP code for a given account.")
@click.argument("account")
def code(account):
    account = storage.get_account(account)
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
    accounts = storage.get_storage()
    accounts[account_name] = {"issuer": issuer, "key": secret_key}
    storage.save_accounts(accounts)


@account.command(help="Remove an account.", name="remove")
@click.argument("name")
def remove_account(name):
    accounts = storage.get_storage()
    accounts.pop(name, None)
    storage.save_accounts(accounts)


@account.command(help="List all accounts.", name="list")
def list_accounts():
    for name in storage.get_storage():
        print(name)


@cli.command(help="Display a QR code for an account.")
@click.argument("account")
def qr(account):
    account = storage.get_account(account)

    totp = pyotp.TOTP(account["key"])
    url = totp.provisioning_uri(issuer_name=account["issuer"])
    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.print_ascii()


if __name__ == "__main__":
    cli()
