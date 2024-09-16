import sys
import time

from multiversx_sdk.core import Token, TokenTransfer, Address
from multiversx_sdk.network_providers.transactions import TransactionOnNetwork
from multiversx_sdk.core import TokenManagementTransactionsFactory, TransactionsFactoryConfig, TransferTransactionsFactory
from multiversx_sdk.network_providers import ProxyNetworkProvider
from multiversx_sdk.wallet import UserSecretKey

SIMULATOR_URL = "http://localhost:8085"
GENERATE_BLOCKS_URL = f"{SIMULATOR_URL}/simulator/generate-blocks"
GENERATE_BLOCKS_UNTIL_EPOCH_REACHED_URL = f"{SIMULATOR_URL}/simulator/generate-blocks-until-epoch-reached"
GENERATE_BLOCKS_UNTIL_TX_PROCESSED = f"{SIMULATOR_URL}/simulator/generate-blocks-until-transaction-processed"

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

    # generate enough blocks to pass an epoch and the ESDT feature to be enabled
    provider.do_post(f"{GENERATE_BLOCKS_UNTIL_EPOCH_REACHED_URL}/1", {})

    # create transaction config and factory
    config = TransactionsFactoryConfig(provider.get_network_config().chain_id)
    transaction_factory = TokenManagementTransactionsFactory(config)

    token_name = "TestToken"
    token_ticker = "TTKN"

    print(f"issuing a fungible ESDT token. Name: {token_name} and ticker: {token_ticker}")

    # create issue transaction
    initial_supply = 100000
    issue_tx = transaction_factory.create_transaction_for_issuing_fungible(
        sender=sender,
        token_name=token_name,
        token_ticker=token_ticker,
        initial_supply=initial_supply,
        num_decimals=1,
        can_pause=False,
        can_wipe=False,
        can_freeze=False,
        can_upgrade=False,
        can_change_owner=False,
        can_add_special_roles=False,
    )
    #the issue token transaction has a cost of 0.05 EGLD, the value is set automatically by the create_transaction_for_issuing_fungible call
    issue_tx.nonce = provider.get_account(sender).nonce
    issue_tx.signature = b"dummy"
    tx_hash = provider.send_transaction(issue_tx)
    print(f"fungible ESDT issue tx hash: {tx_hash}")
    time.sleep(0.5)
    # generate enough blocks until the transaction is completed
    provider.do_post(f"{GENERATE_BLOCKS_UNTIL_TX_PROCESSED}/{tx_hash}", {})

    # get transaction with status (to extract useful information such as generated token identifier)
    tx_from_network = provider.get_transaction(tx_hash, with_process_status=True)
    token_identifier_string = extract_token_identifier(tx_from_network)
    print(f"issued fungible ESDT token with name {token_name} and ticker {token_ticker} received the identifier: {token_identifier_string}\n")

    amount = provider.get_fungible_token_of_account(sender, token_identifier_string)
    if amount.balance != initial_supply:
        sys.exit(f"amount of token from balance is no equal with the initial supply: actual-{amount.balance}, expected-{initial_supply}")

    print(f"the address {sender_bech32} has a balance of {amount.balance} {token_identifier_string}\n")

    key = UserSecretKey.generate()
    receiver_bech32 = key.generate_public_key().to_address("erd").to_bech32()
    receiver = Address.new_from_bech32(receiver_bech32)
    print(f"working with the generated address as receiver: {receiver_bech32}\n")

    print(f"creating a transaction that sends 500 {token_identifier_string} from {sender_bech32} to {receiver_bech32}")

    config = TransactionsFactoryConfig(provider.get_network_config().chain_id)
    tx_factory = TransferTransactionsFactory(config)

    test_token = Token(token_identifier_string, 0)
    token_transfer = TokenTransfer(test_token, 500)
    transfer_tx = tx_factory.create_transaction_for_esdt_token_transfer(
        sender=sender,
        receiver=receiver,
        token_transfers=[token_transfer],
    )
    transfer_tx.nonce = provider.get_account(sender).nonce
    transfer_tx.signature = b"dummy"

    tx_hash = provider.send_transaction(transfer_tx)
    print(f"transfer ESDT tx hash: {tx_hash}\n")
    time.sleep(0.5)

    provider.do_post(f"{GENERATE_BLOCKS_UNTIL_TX_PROCESSED}/{tx_hash}", {})

    amount = provider.get_fungible_token_of_account(sender, token_identifier_string)
    print(f"the address {sender_bech32} has a balance of {amount.balance} {token_identifier_string}")
    amount = provider.get_fungible_token_of_account(receiver, token_identifier_string)
    print(f"the address {receiver_bech32} has a balance of {amount.balance} {token_identifier_string}")


def extract_token_identifier(tx: TransactionOnNetwork) -> str:
    for event in tx.logs.events:
        if event.identifier != "upgradeProperties":
            continue

        decoded_bytes = bytes.fromhex(event.topics[0].hex())
        return decoded_bytes.decode('utf-8')

    return ""

if __name__ == "__main__":
    main()