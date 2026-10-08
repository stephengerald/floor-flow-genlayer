# FloorFlow

Extracts direct room connections from a labeled floor-plan image and answers deterministic shortest-route queries.

## Why this is an intelligent contract

An immutable undirected spatial graph with breadth-first pathfinding, not a document or ledger workflow. The source interpretation runs inside GenLayer consensus; the stored result and read methods are on-chain.

## Scope

Image interpretation cannot certify accessibility, emergency safety, or real-world building geometry.

## Verify

```powershell
python -m pip install -r requirements.txt
genvm-lint check contracts/floor_flow.py
genvm-lint typecheck contracts/floor_flow.py
pytest tests/direct -q
gltest tests/integration/test_studionet.py --network studionet -v -s
```

Live tests submit permanent public StudioNet test transactions; use a fresh test wallet. See EVIDENCE.md for the completed run and explorer links.
