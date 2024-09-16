import sys
import time

from multiversx_sdk import Address
from multiversx_sdk.core import TransactionsFactoryConfig, TransferTransactionsFactory
from multiversx_sdk.network_providers import ProxyNetworkProvider
from multiversx_sdk.wallet import UserSecretKey

SIMULATOR_URL = "http://localhost:8085"
GENERATE_BLOCKS_URL = f"{SIMULATOR_URL}/simulator/generate-blocks"


def main():
    provider = ProxyNetworkProvider(SIMULATOR_URL)

    key = UserSecretKey.generate()
    sender_bech32 = key.generate_public_key().to_address("erd").to_bech32()
    sender = Address.new_from_bech32(sender_bech32)
    print(f"working with the generated address as sender: {sender_bech32}")

    print(f"    requesting user funds for the sender address: {sender_bech32}")
    provider.do_post(f"{SIMULATOR_URL}/transaction/send-user-funds", {"receiver": f"{sender_bech32}"})
    provider.do_post(f"{GENERATE_BLOCKS_URL}/3", {})
    sender_account = provider.get_account(sender)
    print(f"    sender {sender_bech32} has an initial balance of: {sender_account.balance}\n")

    config = TransactionsFactoryConfig(provider.get_network_config().chain_id)
    tx_factory = TransferTransactionsFactory(config)
    amount_egld = 1000000000000000000  # 1 egld

    key = UserSecretKey.generate()
    receiver_bech32 = key.generate_public_key().to_address("erd").to_bech32()
    receiver = Address.new_from_bech32(receiver_bech32)
    print(f"working with the generated address as receiver: {receiver_bech32}\n")

    print(f"creating a transaction that sends 1egld from {sender_bech32} to {receiver_bech32}")

    call_transaction = tx_factory.create_transaction_for_native_token_transfer(
         sender=sender,
         receiver=receiver,
         native_amount=amount_egld,
    )
    call_transaction.nonce = provider.get_account(sender).nonce
    call_transaction.signature = b"dummy"

    tx_hash = provider.send_transaction(call_transaction)
    print(f"move balance tx hash: {tx_hash}\n")
    time.sleep(0.5)

    provider.do_post(f"{GENERATE_BLOCKS_URL}/5", {})

    sender_account = provider.get_account(sender)
    print(f"sender {sender_bech32} has a balance of: {sender_account.balance}")
    # check receiver balance
    receiver_account = provider.get_account(receiver)
    print(f"receiver {receiver_bech32} has a balance of: {receiver_account.balance}")
    if receiver_account.balance != amount_egld:
        sys.exit(f"receiver did not receive the transferred amount"
                  f"expected balance: {amount_egld}, current balance: {receiver_account.balance}")


if __name__ == "__main__":
    main()
