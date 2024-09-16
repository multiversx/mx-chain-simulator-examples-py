import base64
import time
from pathlib import Path

from multiversx_sdk.core import AddressFactory, Address, ContractQueryBuilder
from multiversx_sdk.network_providers.transactions import TransactionOnNetwork
from multiversx_sdk.core import TransactionsFactoryConfig, SmartContractTransactionsFactory
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
    sender = AddressFactory("erd").create_from_bech32(sender_bech32)
    print(f"working with the generated address as sender: {sender_bech32}")

    print(f"    requesting user funds for the sender address: {sender_bech32}")
    provider.do_post(f"{SIMULATOR_URL}/transaction/send-user-funds", {"receiver": f"{sender_bech32}"})
    provider.do_post(f"{GENERATE_BLOCKS_URL}/3", {})
    sender_account = provider.get_account(sender)
    print(f"    sender {sender_bech32} has an initial balance of: {sender_account.balance}\n")

    # generate enough blocks to pass an epoch and the ESDT feature to be enabled
    provider.do_post(f"{GENERATE_BLOCKS_UNTIL_EPOCH_REACHED_URL}/1", {})

    config = TransactionsFactoryConfig(provider.get_network_config().chain_id)
    sc_factory = SmartContractTransactionsFactory(config)

    bytecode = Path("./adder.wasm").read_bytes()
    deploy_tx = sc_factory.create_transaction_for_deploy(
        sender=sender,
        bytecode=bytecode,
        arguments=[0],
        gas_limit=10000000,
        is_upgradeable=True,
        is_readable=True,
        is_payable=True,
        is_payable_by_sc=True
    )
    # set nonce
    deploy_tx.nonce = provider.get_account(sender).nonce
    deploy_tx.signature = b"dummy"
    tx_hash = provider.send_transaction(deploy_tx)
    print(f"deploy smartcontract tx hash: {tx_hash}")
    time.sleep(0.5)
    # generate enough blocks until the transaction is completed
    provider.do_post(f"{GENERATE_BLOCKS_UNTIL_TX_PROCESSED}/{tx_hash}", {})

    # get transaction with status
    tx_from_network = provider.get_transaction(tx_hash, with_process_status=True)
    contract_address = extract_contract_address(tx_from_network)
    contract_address_bech32 = contract_address.to_bech32()
    print(f"deployed smartcontract at address: {contract_address_bech32}")

    query_contract(provider, contract_address)

    print("\n")

    #call the add endpoint to change the internal value in the contract
    value = 10
    contract_address = extract_contract_address(tx_from_network)
    call_transaction = sc_factory.create_transaction_for_execute(
        sender=sender,
        contract=contract_address,
        function="add",
        gas_limit=10000000,
        arguments=[value]
    )
    call_transaction.nonce = provider.get_account(sender).nonce
    call_transaction.signature = b"dummy"

    # send transaction
    tx_hash = provider.send_transaction(call_transaction)
    print(f"sc call tx hash: {tx_hash}")
    time.sleep(0.5)
    # generate enough blocks until the transaction is completed
    provider.do_post(f"{GENERATE_BLOCKS_UNTIL_TX_PROCESSED}/{tx_hash}", {})

    query_contract(provider, contract_address)


def extract_contract_address(tx: TransactionOnNetwork) -> Address:
    factory = AddressFactory("erd")
    for event in tx.logs.events:
        if event.identifier != "SCDeploy":
            continue

        return factory.create_from_hex(event.topics[0].hex())

def query_contract(provider: ProxyNetworkProvider, contract_address: Address):
    # query
    builder = ContractQueryBuilder(
        contract=contract_address,
        function="getSum",
        call_arguments=[],
    )
    query = builder.build()
    response = provider.query_contract(query)
    decoded_bytes = base64.b64decode(response.return_data[0])
    result_int = int.from_bytes(decoded_bytes, byteorder='big')
    print(f"the smartcontract {contract_address.bech32()} returned the value {result_int} when queried the endpoint getSum")

if __name__ == "__main__":
    main()