"""Direct behavior and edge tests for this contract."""

import json
import pytest

def address(value):
    if isinstance(value, (bytes, bytearray)):
        return "0x" + bytes(value).hex()
    return str(value)

def mock(direct_vm, result, pattern=r".*"):
    direct_vm.clear_mocks()
    direct_vm.mock_llm(pattern, json.dumps(result))

def _address(value):
    return "0x" + bytes(value).hex() if isinstance(value, (bytes, bytearray)) else str(value)

def _mock(vm, answer):
    vm.clear_mocks()
    vm.mock_llm(r".*", json.dumps(answer))

def test_floor_flow_routes_and_rejects_unconfirmed_edges(deploy, direct_vm):
    contract = deploy("floor_flow.py")
    mock(direct_vm, {"edges": [[0, 1], [1, 2]]})
    map_id = contract.publish_map("gallery", '["Entrance", "Hall", "Gallery", "Storage"]', b"demo-floorplan-image")
    assert contract.route(map_id, 0, 2) == ["Entrance", "Hall", "Gallery"]
    assert contract.route(map_id, 0, 3) == []
    with direct_vm.expect_revert("room_out_of_range"):
        contract.route(map_id, 0, 4)
    mock(direct_vm, {"edges": [[1, 0]]})
    with direct_vm.expect_revert("edge_value"):
        contract.publish_map("bad", '["Entrance", "Hall"]', b"demo-floorplan-image")

def test_floor_flow_rejects_duplicate_rooms_and_edges(deploy, direct_vm):
    contract = deploy("floor_flow.py")
    with direct_vm.expect_revert("duplicate_room"):
        contract.publish_map("dup", '["Hall", "hall"]', b"map")
    _mock(direct_vm, {"edges": [[0, 1], [0, 1]]})
    with direct_vm.expect_revert("edges_not_canonical"):
        contract.publish_map("edge", '["Entrance", "Hall"]', b"map")
