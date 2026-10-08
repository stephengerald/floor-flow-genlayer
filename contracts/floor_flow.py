# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

"""A bounded image-derived room graph with deterministic route queries."""

from genlayer import *
import hashlib
import json


def _fail(code: str) -> None:
    raise gl.vm.UserError("[EXPECTED] " + code)


def _bad(code: str) -> None:
    raise gl.vm.UserError("[LLM_ERROR] " + code)


class FloorFlow(gl.Contract):
    maps: TreeMap[str, str]

    def __init__(self):
        pass

    @gl.public.write
    def publish_map(self, key: str, rooms_json: str, image_data: bytes) -> str:
        clean_key = key.strip().lower()
        if not 1 <= len(clean_key) <= 40 or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in clean_key):
            _fail("invalid_key")
        map_id = str(gl.message.sender_address).lower() + ":" + clean_key
        if self.maps.get(map_id, ""):
            _fail("map_exists")
        try:
            rooms = json.loads(rooms_json)
        except (TypeError, ValueError):
            _fail("invalid_rooms_json")
        if not isinstance(rooms, list) or not 2 <= len(rooms) <= 10:
            _fail("room_count")
        if any(not isinstance(r, str) or not 1 <= len(r.strip()) <= 50 for r in rooms):
            _fail("invalid_room")
        if len({r.strip().lower() for r in rooms}) != len(rooms):
            _fail("duplicate_room")
        if not 1 <= len(image_data) <= 150_000:
            _fail("image_size")
        prompt = (
            "Inspect this labeled floor plan. Return JSON exactly {\"edges\":[[a,b],...]}, "
            "where each pair is a DIRECT walkable doorway between supplied room indices. "
            "Use zero-based indices, each pair sorted ascending, and the entire list unique and "
            "lexicographically sorted. Do not infer a doorway through a wall. "
            "Rooms: " + json.dumps(rooms)
        )

        def parse(value):
            if not isinstance(value, dict) or set(value) != {"edges"} or not isinstance(value["edges"], list):
                _bad("edges_shape")
            edges = value["edges"]
            if not 1 <= len(edges) <= 20:
                _bad("edge_count")
            for edge in edges:
                if not isinstance(edge, list) or len(edge) != 2:
                    _bad("edge_shape")
                if any(type(x) is not int or x < 0 or x >= len(rooms) for x in edge) or edge[0] >= edge[1]:
                    _bad("edge_value")
            if edges != sorted(edges) or len({tuple(e) for e in edges}) != len(edges):
                _bad("edges_not_canonical")
            return edges

        def leader_fn():
            return parse(gl.nondet.exec_prompt(prompt, images=[image_data], response_format="json"))

        def validator_fn(leader_result):
            if not isinstance(leader_result, gl.vm.Return):
                return False
            try:
                candidate = leader_result.calldata
                return parse({"edges": candidate}) == leader_fn()
            except Exception:
                return False

        edges = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        self.maps[map_id] = json.dumps(
            {"rooms": rooms, "edges": edges, "image_sha256": hashlib.sha256(image_data).hexdigest()},
            sort_keys=True, separators=(",", ":"),
        )
        return map_id

    @gl.public.view
    def get_map(self, map_id: str) -> dict:
        raw = self.maps.get(map_id, "")
        if not raw:
            _fail("map_missing")
        return json.loads(raw)

    @gl.public.view
    def route(self, map_id: str, start: u256, destination: u256) -> list[str]:
        record = self.get_map(map_id)
        a = int(start)
        b = int(destination)
        rooms = record["rooms"]
        if a >= len(rooms) or b >= len(rooms):
            _fail("room_out_of_range")
        neighbors = [[] for _ in rooms]
        for x, y in record["edges"]:
            neighbors[x].append(y)
            neighbors[y].append(x)
        queue = [a]
        paths = {a: [a]}
        for node in queue:
            if node == b:
                return [rooms[index] for index in paths[node]]
            for next_node in sorted(neighbors[node]):
                if next_node not in paths:
                    paths[next_node] = paths[node] + [next_node]
                    queue.append(next_node)
        return []
