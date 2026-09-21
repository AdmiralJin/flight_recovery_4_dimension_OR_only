from backend.schemas.workbench import CompilePreview, DraftDocument, SnapshotRecord
from backend.workbench.comparison import build_comparison


def test_arrival_only_delay_is_changed_and_partitions_every_flight():
    scenario = {
        "flights": [
            {
                "flight_id": "F1",
                "origin": "AAA",
                "destination": "BBB",
                "sched_dep": "2026-01-01T01:00:00Z",
                "sched_arr": "2026-01-01T02:00:00Z",
                "duration": 60,
                "original_aircraft": "A1",
                "original_crew": "C1",
            },
            {
                "flight_id": "F2",
                "origin": "BBB",
                "destination": "CCC",
                "sched_dep": "2026-01-01T03:00:00Z",
                "sched_arr": "2026-01-01T04:00:00Z",
                "duration": 60,
                "original_aircraft": "A1",
                "original_crew": "C1",
            },
        ],
        "aircraft": [],
        "crew": [],
        "passengers": [],
        "airport_intervals": [],
    }
    snapshot = SnapshotRecord(
        snapshot_id="S1",
        draft_id="D1",
        revision_id="R1",
        content_hash="a" * 64,
        created_at="2026-01-01T00:00:00Z",
        solve_request={},
        compile_preview=CompilePreview(
            valid=True,
            draft_hash="b" * 64,
            compiled_hash="a" * 64,
            effective_scenario=scenario,
            solve_request={},
        ),
        draft_document=DraftDocument(name="test", scenario=scenario),
    )
    result = {
        "status": "optimal",
        "resolved_flights": [
            {
                "resolved": {
                    "flight_id": "F1",
                    "status": "operated",
                    "recovered_origin": "AAA",
                    "recovered_destination": "BBB",
                    "recovered_dep": "2026-01-01T01:00:00Z",
                    "recovered_arr": "2026-01-01T02:10:00Z",
                    "departure_delay_minutes": 0,
                    "arrival_delay_minutes": 10,
                    "aircraft_id": "A1",
                    "crew_id": "C1",
                }
            },
            {
                "resolved": {
                    "flight_id": "F2",
                    "status": "operated",
                    "recovered_origin": "BBB",
                    "recovered_destination": "CCC",
                    "recovered_dep": "2026-01-01T03:00:00Z",
                    "recovered_arr": "2026-01-01T04:00:00Z",
                    "departure_delay_minutes": 0,
                    "arrival_delay_minutes": 0,
                    "aircraft_id": "A1",
                    "crew_id": "C1",
                }
            },
        ],
    }
    comparison = build_comparison(snapshot, result)
    assert comparison["counts"]["changed_flights"] == 1
    assert comparison["counts"]["unchanged_flights"] == 1
    assert comparison["counts"]["total_flights"] == 2
    first = next(item for item in comparison["flights"] if item["flight_id"] == "F1")
    assert "time_changed" in first["change_flags"]
