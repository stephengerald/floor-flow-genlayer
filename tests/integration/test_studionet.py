"""Opt-in live StudioNet transactions and latest-final readback for each contract."""

import base64
import hashlib
import io
import json
from pathlib import Path
import time

from genlayer_py import create_account
from gltest import get_contract_factory
from gltest.assertions import tx_execution_succeeded
from gltest.clients import get_gl_client
from gltest.types import TransactionHashVariant, TransactionStatus
from gltest.utils import extract_contract_address
from PIL import Image, ImageDraw, ImageFont


CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


def _ok(receipt):
    assert tx_execution_succeeded(receipt), json.dumps(receipt, default=str)
    assert receipt.get("status_name") == TransactionStatus.FINALIZED.value, json.dumps(receipt, default=str)
    assert receipt.get("result_name") == "MAJORITY_AGREE", (
        f"Finalized transaction was not accepted by consensus: {receipt.get('result_name')} "
        f"tx={receipt.get('hash')}"
    )
    return receipt


def _deploy(filename):
    account = create_account()
    source = CONTRACTS / filename
    factory = get_contract_factory(contract_file_path=source)
    receipt = _ok(factory.deploy_contract_tx(args=[], account=account, wait_transaction_status=TransactionStatus.FINALIZED))
    address = extract_contract_address(receipt)
    contract = factory.build_contract(address, account=account)
    print("LIVE_DEPLOY=" + json.dumps({"contract": filename, "address": str(address), "tx": receipt["hash"]}))
    return account, contract, receipt, source


def _call(method, *args):
    last_error = None
    for attempt in range(8):
        try:
            return method(args=list(args)).call(transaction_hash_variant=TransactionHashVariant.LATEST_FINAL)
        except Exception as error:
            last_error = error
            if attempt != 7:
                time.sleep(3)
    raise AssertionError(f"latest-final readback failed after retries: {last_error}")


def _write(method, *args):
    receipt = _ok(method(args=list(args)).transact(wait_transaction_status=TransactionStatus.FINALIZED))
    print("LIVE_TX=" + str(receipt["hash"]))
    return receipt


def _evidence(name, account, contract, deployment, transactions, source, observed):
    code = None
    schema = None
    for attempt in range(6):
        try:
            code = _rpc("gen_getContractCode", [str(contract.address)])
            schema = _rpc("gen_getContractSchema", [str(contract.address)])
            if code and isinstance(schema, dict) and isinstance(schema.get("methods"), dict):
                break
        except Exception:
            if attempt == 5:
                raise
        time.sleep(4)
    assert base64.b64decode(code, validate=True) == source.read_bytes()
    assert isinstance(schema.get("methods"), dict) and schema["methods"]
    print("LIVE_EVIDENCE=" + json.dumps({
        "name": name,
        "network": "studionet",
        "chain_id": 61999,
        "address": str(contract.address),
        "account_address": str(account.address),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "deployed_source_exact": True,
        "schema_methods": sorted(schema["methods"]),
        "deployment_tx": deployment["hash"],
        "action_txs": [tx["hash"] for tx in transactions],
        "observed": observed,
    }, sort_keys=True, default=str))


def _rpc(method, params):
    decoded = get_gl_client().provider.make_request(method=method, params=params)
    if decoded.get("error"):
        raise AssertionError(decoded["error"])
    return decoded["result"]


def _font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _receipt_png():
    image = Image.new("RGB", (750, 460), "white")
    draw = ImageDraw.Draw(image)
    font = _font(30)
    lines = ["SPLITSLIP DEMO RECEIPT", "Soup                     $9.00",
             "Pasta                   $15.00", "Tax                       $1.01",
             "Tip                       $1.00", "TOTAL                    $26.01"]
    for index, line in enumerate(lines):
        draw.text((35, 25 + index * 68), line, fill="black", font=font)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _floor_png():
    image = Image.new("RGB", (900, 440), "white")
    draw = ImageDraw.Draw(image)
    font = _font(32)
    boxes = [(40, 120, 270, 330), (335, 120, 565, 330), (630, 120, 860, 330)]
    names = ["Entrance", "Hall", "Gallery"]
    for box, name in zip(boxes, names):
        draw.rectangle(box, outline="black", width=7)
        draw.text((box[0] + 20, box[1] + 75), name, fill="black", font=font)
    draw.line((270, 225, 335, 225), fill="black", width=15)
    draw.line((565, 225, 630, 225), fill="black", width=15)
    draw.text((274, 260), "DOOR", fill="black", font=_font(18))
    draw.text((570, 260), "DOOR", fill="black", font=_font(18))
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()



def test_floor_flow_studionet():
    account, contract, deploy_tx, source = _deploy("floor_flow.py")
    action = _write(contract.publish_map, "demo-gallery", '["Entrance","Hall","Gallery"]', _floor_png())
    map_id = str(account.address).lower() + ":demo-gallery"
    record = _call(contract.get_map, map_id)
    path = _call(contract.route, map_id, 0, 2)
    assert record["edges"] == [[0, 1], [1, 2]]
    assert path == ["Entrance", "Hall", "Gallery"]
    _evidence("FloorFlow", account, contract, deploy_tx, [action], source,
              {"edges": record["edges"], "route": path})
