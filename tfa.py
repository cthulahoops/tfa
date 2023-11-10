import click
import pyotp
import qrcode
import json

ACCOUNTS = json.load(open("/home/akelly/.tfa"))


@click.group()
def cli():
    pass


@cli.command(help="Show a TOTP code for a given account.")
@click.argument("account")
def code(account):
    if account not in ACCOUNTS:
        print(f"Account {account} not found in: {' '.join(ACCOUNTS.keys())}")

    account = ACCOUNTS[account]
    totp = pyotp.TOTP(account["key"])
    print(f"{account['issuer']}: {totp.now()}")


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
