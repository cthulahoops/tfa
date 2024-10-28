# TFA CLI Tool

A command-line tool for managing two-factor authentication (2FA) TOTP codes.

## Why did I build this?

* I wanted to understand how TOTP codes work. I don't like trusting access to my accounts to a black box which I don't understand.
* I don't keep my phone with me all the time.
* I'm worried about losing access to my accounts if I lose my phone.

I feel far more comfortable with TOTP codes now!

## Should you use this?

Maybe? This probably isn't best practice for two factor authentication codes. The default
assumption is that phones have better security than computers. Depending on how you manage
passwords, and access to your e-mail someone with access to your computer probably has the ability
to access your accounts.

The secret database is not encrypted. It a simple json file that gets rewritten on every
modification. It might lose your secrets. You should keep backups, and probably use the qr code
feature to add accounts an authenticator app.

I'm also not a security expert. I'm just a programmer who wanted to understand TOTP. Maybe you
should use a standard tool instead.

Use at your own risk.

## Installation

```bash
pip install tfa
```

There is no default location for the database because the point is to make secret management
less opaque than typical authentication apps. Set a preferred location in your shell configuration.

```bash
export TFA_STORAGE_PATH=~/.config/tfa/accounts.json
```

The secrets are stored in a simple json file with no encryption.

## Usage

### Add a new account
```bash
tfa add <account_name> <secret_key>

# With custom issuer name
tfa add <account_name> <secret_key> --issuer "Custom Name"

# Force overwrite existing account
tfa add <account_name> <secret_key> -f
```

### Get TOTP code
```bash
tfa code <account_name>
```

### List accounts
```bash
tfa list
```

### Remove account
```bash
tfa remove <account_name>
```

### Generate QR Code
Generate a QR code to scan with other authenticator apps:

```bash
tfa qr <account_name>
```

## Examples

```bash
# Add a new GitHub account
tfa add github JBSWY3DPEHPK3PXP --issuer "GitHub"

# Get current code
tfa code github
# Output: GitHub: 123456

# List all accounts
tfa list
# Output: github

# Generate QR code
tfa qr github
```
