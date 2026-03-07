import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from xrpl.clients import JsonRpcClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import TrustSet, Payment
from xrpl.models.amounts import IssuedCurrencyAmount
from xrpl.transaction import submit_and_wait
from xrpl.models.requests import AccountLines

# --- 1. FORCE LOAD ENV ---
# This looks in the same folder as this .py file
script_dir = Path(__file__).parent
env_path = script_dir / '.env'

if not env_path.exists():
    print(f"ERROR: .env file NOT found at {env_path}")
    exit()

load_dotenv(dotenv_path=env_path)

# --- 2. VALIDATE KEYS ---
def get_env_var(var_name):
    val = os.getenv(var_name)
    if not val:
        print(f"ERROR: Variable '{var_name}' is missing in .env")
        exit()
    return val.strip()

MY_SECRET = get_env_var("MY_WALLET_SECRET")
ISSUER_ADDR = get_env_var("ISSUER_WALLET_ADDR")
ISSUER_SECRET = get_env_var("ISSUER_WALLET_SECRET")

# --- 3. INITIALIZE ---
client = JsonRpcClient("https://s.devnet.rippletest.net:51234/")
my_wallet = Wallet.from_secret(MY_SECRET)
issuer_wallet = Wallet.from_secret(ISSUER_SECRET)

def to_hex(currency):
    return currency.encode("utf-8").hex().upper().ljust(40, '0')

RLUSD_HEX = to_hex("RLUSD")

# --- 4. THE BOOTSTRAPPER ---
def setup_everything():
    print("Starting Bootstrap...")

    # A. Check Trust Line
    print("Checking Trust Line...")
    lines_req = AccountLines(account=my_wallet.classic_address)
    lines_res = client.request(lines_req)
    has_trust = any(
        l['account'] == ISSUER_ADDR and l['currency'] == RLUSD_HEX 
        for l in lines_res.result.get('lines', [])
    )

    if not has_trust:
        print("No Trust Line found. Creating one now...")
        ts_tx = TrustSet(
            account=my_wallet.classic_address,
            limit_amount=IssuedCurrencyAmount(
                currency=RLUSD_HEX,
                issuer=ISSUER_ADDR,
                value="1000000"
            )
        )
        submit_and_wait(ts_tx, client, my_wallet)
        print("Trust Line established!")
    else:
        print("Trust Line already exists.")

    # B. Check RLUSD Balance (Mint if 0)
    print("Checking RLUSD balance...")
    # (Simplified: just sending 100 RLUSD to ensure you have some)
    mint_tx = Payment(
        account=issuer_wallet.classic_address,
        destination=my_wallet.classic_address,
        amount=IssuedCurrencyAmount(
            currency=RLUSD_HEX,
            issuer=ISSUER_ADDR,
            value="100"
        )
    )
    submit_and_wait(mint_tx, client, issuer_wallet)
    print("Minted 100 RLUSD to your wallet.")

if __name__ == "__main__":
    setup_everything()
    print(f"\nSUCCESS! Your wallet {my_wallet.classic_address} is ready for the Blockathon.")
