import os
import requests
from dotenv import load_dotenv
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import TrustSet, Payment
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.transaction import submit_and_wait

# 1. Setup
load_dotenv()
client = JsonRpcClient("https://s.devnet.rippletest.net:51234/")

print(f"DEBUG: Loaded secret is: {os.getenv('DEVNET_SECRET')}")
my_wallet = Wallet.from_secret(os.getenv("DEVNET_SECRET"))
issuer_wallet = Wallet.create()

def fund_account(address):
    # The official Devnet Faucet
    faucet_url = "https://faucet.devnet.rippletest.net/accounts"
    requests.post(faucet_url, json={"destination": address})
    print(f"Funded {address}")

# Activate both accounts
fund_account(my_wallet.classic_address)
fund_account(issuer_wallet.classic_address)

def to_hex(currency):
    return currency.encode("utf-8").hex().upper().ljust(40, '0')

# 2. Establish Trust Line (my_wallet trusts issuer_wallet)
trust_set = TrustSet(
    account=my_wallet.classic_address,
    limit_amount=IssuedCurrencyAmount(
        currency=to_hex("RLUSD"),
        issuer=issuer_wallet.classic_address,
        value="1000000"
    )
)
submit_and_wait(trust_set, client, my_wallet)

# 3. Mint/Send RLUSD (issuer_wallet sends to my_wallet)
mint = Payment(
    account=issuer_wallet.classic_address,
    destination=my_wallet.classic_address,
    amount=IssuedCurrencyAmount(
        currency=to_hex("RLUSD"),
        issuer=issuer_wallet.classic_address,
        value="50"
    )
)
submit_and_wait(mint, client, issuer_wallet)

print("SUCCESS: You now have 50 RLUSD in your wallet!")
