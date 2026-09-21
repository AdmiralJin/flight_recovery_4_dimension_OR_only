from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from itertools import product
from pathlib import Path
from typing import Any

from backend.application.case_service import load_case
from backend.application.solve_service import ALGORITHM, default_profile_ids, solve_readiness
from backend.schemas.columns import RecoveryColumns
from backend.schemas.result import SolveRequest
from backend.schemas.scenario import Scenario


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_ROOT = ROOT / "data" / "validation_suite"


CONSTRAINT_IDS = (
    "SRM-C01-FLIGHT-COVERAGE",
    "SRM-C02-STRATEGIC-FLIGHT",
    "SRM-C03-ARRIVAL-CAPACITY",
    "SRM-C04-DEPARTURE-CAPACITY",
    "SRM-C05-GATE-INVENTORY",
    "SRM-C06-MARKET-SEAT",
    "ARM-C01-AIRCRAFT-STRING-SELECTION",
    "ARM-C02-FLIGHT-OPTION-COVERAGE",
    "ARM-C03-TERMINAL-STATION",
    "ARM-C04-MAINTENANCE",
    "ARM-C05-STRING-FEASIBILITY",
    "CRM-C01-CREW-PAIRING-SELECTION",
    "CRM-C02-FLIGHT-OPTION-COVERAGE",
    "CRM-C03-NONREQUIRED-REVENUE-PROHIBITION",
    "CRM-C04-CREW-FEASIBILITY",
    "CRM-C05-TERMINAL-OR-OWNERSHIP",
    "PRM-C01-PASSENGER-GROUP-SELECTION",
    "PRM-C02-SCHEDULE-CONSISTENCY",
    "PRM-C03-SEAT-CAPACITY",
    "PRM-C04-ITINERARY-FEASIBILITY",
)


@dataclass(frozen=True)
class ScaleProfile:
    profile_id: str
    label: str
    target_runtime: str
    airport_count: int
    operating_aircraft: int
    reserve_aircraft: int
    reserve_crew: int
    passenger_groups: int
    delay_minutes: tuple[int, ...]
    disrupted_fraction: float
    seed: int
    calibration_status: str = "uncalibrated"

    @property
    def flight_count(self) -> int:
        return self.operating_aircraft * 4

    @property
    def crew_count(self) -> int:
        return self.operating_aircraft + self.reserve_crew

    @property
    def aircraft_count(self) -> int:
        return self.operating_aircraft + self.reserve_aircraft


SCALE_PROFILES = (
    ScaleProfile(
        "P1-seconds",
        "几秒级 / 紧凑演示",
        "2-8 seconds",
        4,
        3,
        0,
        0,
        12,
        (30,),
        0.34,
        101,
        "calibrated_local_1.3_to_1.7_seconds",
    ),
    ScaleProfile(
        "P2-tens-seconds",
        "几十秒级 / 标准演示",
        "30-90 seconds",
        4,
        3,
        0,
        0,
        12,
        (30,),
        0.34,
        202,
        "calibrated_local_70s_budget_aborted",
    ),
    ScaleProfile(
        "P3-minutes",
        "几分钟级 / 丰富演示",
        "2-8 minutes",
        6,
        5,
        1,
        1,
        30,
        (30,),
        0.40,
        303,
    ),
    ScaleProfile(
        "P4-tens-minutes",
        "几十分钟级压力",
        "15-45 minutes",
        8,
        10,
        2,
        3,
        80,
        (30, 60),
        0.45,
        404,
    ),
    ScaleProfile(
        "P5-hours",
        "小时级压力",
        "1-3 hours",
        12,
        18,
        3,
        6,
        250,
        (30, 60, 90),
        0.50,
        505,
    ),
)


CALIBRATION_RESULTS: dict[str, Any] = {
    "reference_environment": {
        "date": "2026-09-21",
        "os": "Windows",
        "cpu": "12th Gen Intel Core i7-12700H (14 cores / 20 logical processors)",
        "memory_gib": 15.7,
        "solver": "Gurobi 13.0.3",
        "license": "restricted size-limited non-production license",
    },
    "results": {
        "P1-seconds": {
            "status": "optimal",
            "wall_seconds": 1.308,
            "objective": 18080.0,
            "lower_bound": 18080.0,
            "upper_bound": 18080.0,
            "gap": 0.0,
            "integrated_audit_pass": True,
            "note": "Single representative local run; prior probes were approximately 1.5-1.7 seconds.",
        },
        "P2-tens-seconds": {
            "status": "aborted",
            "wall_seconds": 70.074,
            "objective": None,
            "lower_bound": 120.0,
            "upper_bound": 600.0,
            "gap": 480.0,
            "integrated_audit_pass": None,
            "terminal_reason": "phase11_aborted",
            "note": "70-second budget probe; verifies bounded progress and controlled termination, not optimal completion.",
        },
        "P3-minutes": {"status": "not_run", "note": "Requires scheduled calibration."},
        "P4-tens-minutes": {"status": "not_run", "note": "Requires scheduled calibration and a full license."},
        "P5-hours": {"status": "not_run", "note": "Requires scheduled calibration and a full license."},
    },
}


MICRO_CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "micro-integrated-benchmark",
        "label": "综合恢复人工基准",
        "source_type": "catalog",
        "source_id": "benchmark-disruption-recovery",
        "import_kind": "solve_bundle",
        "category": "综合算法",
        "constraints": list(CONSTRAINT_IDS),
        "algorithms": ["integrated", "benders", "column_generation"],
        "expected": {"status": "optimal", "objective_total": 18080.0},
        "human_check": "3 个航班延误共 80 分钟，旅客加权延误 1800，目标值 18080。",
    },
    {
        "case_id": "micro-crew-integrality",
        "label": "机组整数性与分支定价",
        "source_type": "catalog",
        "source_id": "crew-recovery-integrality",
        "import_kind": "solve_bundle",
        "category": "机组",
        "constraints": [item for item in CONSTRAINT_IDS if item.startswith("CRM-")],
        "algorithms": ["branch_and_price", "crew_integrality"],
        "expected": {"status": "optimal", "objective_total": 95200.0},
        "human_check": "根节点 LP 存在整数缺口，9 个机组分支节点闭合到 95200。",
    },
    {
        "case_id": "micro-passenger-capacity-binding",
        "label": "旅客余座容量绑定",
        "source_type": "catalog",
        "source_id": "passenger-capacity-constrained",
        "import_kind": "solve_bundle",
        "category": "旅客",
        "constraints": [
            "PRM-C01-PASSENGER-GROUP-SELECTION",
            "PRM-C02-SCHEDULE-CONSISTENCY",
            "PRM-C03-SEAT-CAPACITY",
            "PRM-C04-ITINERARY-FEASIBILITY",
        ],
        "algorithms": ["passenger_recovery"],
        "expected": {"status": "optimal", "objective_total": 1010.0},
        "human_check": "原始候选余座为 0，10 人旅客组迫使航班延误 10 分钟。",
    },
    {
        "case_id": "micro-passenger-capacity-relaxed",
        "label": "旅客容量单变量放宽",
        "source_type": "catalog",
        "source_id": "passenger-capacity-relaxed",
        "import_kind": "solve_bundle",
        "category": "旅客",
        "constraints": ["PRM-C03-SEAT-CAPACITY"],
        "algorithms": ["sensitivity"],
        "expected": {"status": "optimal", "objective_total": 0.0},
        "human_check": "仅把原始候选余座从 0 改为 10，最优目标从 1010 降为 0。",
    },
    {
        "case_id": "micro-delay-unserved-tradeoff",
        "label": "延误与未承运成本权衡",
        "source_type": "catalog",
        "source_id": "delay-cost-cancellation-tradeoff",
        "import_kind": "solve_bundle",
        "category": "成本",
        "constraints": [
            "PRM-C01-PASSENGER-GROUP-SELECTION",
            "PRM-C02-SCHEDULE-CONSISTENCY",
            "PRM-C03-SEAT-CAPACITY",
        ],
        "algorithms": ["cost_sensitivity"],
        "expected": {"status": "optimal", "objective_total": 25000.0},
        "human_check": "提高航班延误单价后，保留原计划并承担 10 人未承运成本。",
    },
    {
        "case_id": "micro-solve-ready-infeasible",
        "label": "输入就绪但优化不可行",
        "source_type": "catalog",
        "source_id": "solve-ready-infeasible",
        "import_kind": "solve_bundle",
        "category": "边界",
        "constraints": [
            "SRM-C01-FLIGHT-COVERAGE",
            "ARM-C02-FLIGHT-OPTION-COVERAGE",
            "CRM-C02-FLIGHT-OPTION-COVERAGE",
        ],
        "algorithms": ["feasibility"],
        "expected": {"status": "infeasible", "objective_total": None},
        "human_check": "结构和配置完整，但候选集合无法形成联合可行恢复。",
    },
    {
        "case_id": "micro-scenario-only-minimal",
        "label": "最小有效 Scenario",
        "source_type": "catalog",
        "source_id": "scenario-only-minimal",
        "import_kind": "scenario",
        "category": "输入校验",
        "constraints": ["SRM-C03-ARRIVAL-CAPACITY", "SRM-C04-DEPARTURE-CAPACITY"],
        "algorithms": ["validation"],
        "expected": {"scenario_valid": True, "solve_ready": False},
        "human_check": "Scenario 有效，但没有候选、容量和算法配置，因此不能求解。",
    },
    {
        "case_id": "micro-invalid-missing-airport",
        "label": "无效机场引用",
        "source_type": "catalog",
        "source_id": "invalid-missing-airport",
        "import_kind": "scenario",
        "category": "输入校验",
        "constraints": [],
        "algorithms": ["negative_validation"],
        "expected": {"scenario_valid": False, "error_code": "unknown_airport"},
        "human_check": "航班引用未声明机场，必须在求解前被拒绝。",
    },
    {
        "case_id": "micro-scenario-validation-rich",
        "label": "多实体 Scenario 校验",
        "source_type": "scenario_file",
        "source_id": "phase1_validation_001",
        "import_kind": "scenario",
        "category": "输入校验",
        "constraints": [],
        "algorithms": ["validation", "visualization"],
        "expected": {"scenario_valid": True, "solve_ready": False},
        "human_check": "5 机场、12 航班、6 飞机、6 机组和 8 旅客组的结构校验样例。",
    },
    {
        "case_id": "micro-basic-editor",
        "label": "编辑器与传播基础样例",
        "source_type": "scenario_file",
        "source_id": "toy_case_001",
        "import_kind": "scenario",
        "category": "输入校验",
        "constraints": [],
        "algorithms": ["validation", "visualization"],
        "expected": {"scenario_valid": True, "solve_ready": False},
        "human_check": "用于导入、编辑、导出和扰动传播的最小综合 Scenario。",
    },
    {
        "case_id": "micro-aircraft-coupling",
        "label": "飞机对计划选择的反向耦合",
        "source_type": "artifact",
        "source_id": "toy_case_004",
        "capacity_file": "toy_case_004_capacity.json",
        "import_kind": "solve_bundle",
        "category": "飞机",
        "constraints": [item for item in CONSTRAINT_IDS if item.startswith("ARM-")],
        "algorithms": ["aircraft_recovery", "integrated"],
        "expected": {"status": "optimal"},
        "human_check": "比较原计划与延误候选，观察动态飞机列如何限制计划选择。",
    },
    {
        "case_id": "micro-scope-closure",
        "label": "恢复范围闭包",
        "source_type": "artifact",
        "source_id": "toy_case_006_scope",
        "capacity_file": "toy_case_006_scope_capacity.json",
        "import_kind": "solve_bundle",
        "category": "计划",
        "constraints": [
            "SRM-C01-FLIGHT-COVERAGE",
            "ARM-C02-FLIGHT-OPTION-COVERAGE",
            "CRM-C02-FLIGHT-OPTION-COVERAGE",
            "PRM-C02-SCHEDULE-CONSISTENCY",
        ],
        "algorithms": ["scope", "integrated"],
        "expected": {"status": "optimal", "objective_total": 2040.0},
        "human_check": "受扰组件需要两班各延误 20 分钟，独立组件保持原计划。",
    },
    {
        "case_id": "micro-aircraft-string-generation",
        "label": "飞机路径生成",
        "source_type": "artifact",
        "source_id": "toy_case_007_string_generator",
        "import_kind": "solve_bundle",
        "category": "飞机",
        "constraints": [
            "ARM-C01-AIRCRAFT-STRING-SELECTION",
            "ARM-C02-FLIGHT-OPTION-COVERAGE",
            "ARM-C03-TERMINAL-STATION",
            "ARM-C04-MAINTENANCE",
            "ARM-C05-STRING-FEASIBILITY",
        ],
        "algorithms": ["aircraft_string_generation"],
        "expected": {"status": "optimal", "objective_total": 0.0},
        "human_check": "覆盖机型、衔接、终到站、维修和调机路径边界。",
    },
    {
        "case_id": "micro-passenger-itinerary-generation",
        "label": "旅客行程生成",
        "source_type": "artifact",
        "source_id": "toy_case_009_passenger_itinerary_generator",
        "import_kind": "solve_bundle",
        "category": "旅客",
        "constraints": [item for item in CONSTRAINT_IDS if item.startswith("PRM-")],
        "algorithms": ["passenger_itinerary_generation"],
        "expected": {"status": "optimal", "objective_total": 0.0},
        "human_check": "覆盖直达、中转、最小衔接、最大航段和未承运行程。",
    },
    {
        "case_id": "micro-fixed-column-benders",
        "label": "固定列 Benders 行为",
        "source_type": "artifact",
        "source_id": "toy_case_010_fixed_column_benders",
        "capacity_file": "toy_case_010_fixed_column_benders_capacity.json",
        "import_kind": "solve_bundle",
        "category": "算法",
        "constraints": ["SRM-C01-FLIGHT-COVERAGE", "PRM-C03-SEAT-CAPACITY"],
        "algorithms": ["benders"],
        "expected": {"status": "optimal"},
        "human_check": "保留用于观察 Benders 可行割和最优割；最终动态列入口可能得到更低目标。",
    },
    {
        "case_id": "micro-aircraft-column-generation",
        "label": "飞机列生成定价",
        "source_type": "artifact",
        "source_id": "toy_case_011_aircraft_string_column_generation",
        "import_kind": "solve_bundle",
        "category": "飞机",
        "constraints": [item for item in CONSTRAINT_IDS if item.startswith("ARM-")],
        "algorithms": ["aircraft_column_generation"],
        "expected": {"status": "optimal", "objective_total": 0.0},
        "human_check": "初始调机列成本为 300，负约化成本列把飞机子问题降为 0。",
    },
    {
        "case_id": "micro-crew-column-generation",
        "label": "机组列生成定价",
        "source_type": "artifact",
        "source_id": "toy_case_012_crew_pairing_column_generation",
        "import_kind": "solve_bundle",
        "category": "机组",
        "constraints": [item for item in CONSTRAINT_IDS if item.startswith("CRM-")],
        "algorithms": ["crew_column_generation"],
        "expected": {"status": "optimal", "objective_total": 150.0},
        "human_check": "定价加入更便宜机组任务，正式综合入口的总目标为 150。",
    },
    {
        "case_id": "micro-benders-column-generation",
        "label": "Benders 与列生成组合",
        "source_type": "artifact",
        "source_id": "toy_case_013_benders_column_generation",
        "capacity_file": "toy_case_013_benders_column_generation_capacity.json",
        "import_kind": "solve_bundle",
        "category": "算法",
        "constraints": list(CONSTRAINT_IDS),
        "algorithms": ["benders", "column_generation"],
        "expected": {"status": "optimal", "objective_total": 220.0},
        "human_check": "三个计划候选分别对应资源不可行、旅客高成本和综合最优，最优为 220。",
    },
    {
        "case_id": "micro-crew-root-integrality",
        "label": "机组根节点整数缺口",
        "source_type": "artifact",
        "source_id": "toy_case_015_crew_integrality",
        "import_kind": "solve_bundle",
        "category": "机组",
        "constraints": [item for item in CONSTRAINT_IDS if item.startswith("CRM-")],
        "algorithms": ["crew_integrality", "branch_and_price"],
        "cost_overrides": {"crew_reassignment": 100.0, "deadhead_per_minute": 1.0},
        "expected": {"status": "optimal"},
        "human_check": "专用机组子问题根 LP 为 195、整数最优为 200；综合入口用于结构导入检查。",
    },
    {
        "case_id": "micro-branch-and-price",
        "label": "完整 Branch-and-Price",
        "source_type": "artifact",
        "source_id": "toy_case_016_benders_branch_and_price",
        "capacity_file": "toy_case_016_benders_branch_and_price_capacity.json",
        "import_kind": "solve_bundle",
        "category": "算法",
        "constraints": list(CONSTRAINT_IDS),
        "algorithms": ["benders", "column_generation", "branch_and_price"],
        "cost_overrides": {"crew_reassignment": 100.0, "deadhead_per_minute": 1.0},
        "expected": {"status": "optimal", "objective_total": 95200.0},
        "human_check": "必须通过机组分支闭合整数缺口，最终目标 95200。",
    },
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _synthetic_capacity(scenario: dict[str, Any], columns: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "capacity_profile_id": f"{scenario['scenario_id']}_validation_capacity",
        "scenario_id": scenario["scenario_id"],
        "source": "test_fixture",
        "units": "seats",
        "seat_capacity_by_option_id": {
            option["option_id"]: 999999
            for option in columns["flight_options"]
            if option["operation_type"] == "operate"
        },
        "notes": ["Synthetic non-binding capacity for validation-suite packaging."],
    }


def _artifact_bundle(spec: dict[str, Any]) -> dict[str, Any]:
    source_id = spec["source_id"]
    scenario = _read_json(ROOT / "data" / "examples" / f"{source_id}.json")
    columns = _read_json(ROOT / "data" / "columns" / f"{source_id}_columns.json")
    columns["aircraft_strings"] = []
    columns["crew_pairings"] = []
    capacity_file = spec.get("capacity_file")
    capacity = (
        _read_json(ROOT / "data" / "capacities" / capacity_file)
        if capacity_file
        else _synthetic_capacity(scenario, columns)
    )
    request = SolveRequest(
        schema_version="1.0.0",
        scenario=scenario,
        recovery_columns=columns,
        capacity_profile=capacity,
        cost_profile_id="phase2_test_v1",
        cost_overrides=spec.get("cost_overrides", {}),
        algorithm=ALGORITHM,
        profile_ids=default_profile_ids(),
    ).model_dump(mode="json")
    readiness = solve_readiness(request)
    if not readiness["solve_ready"]:
        raise ValueError(f"{spec['case_id']} is not solve-ready: {readiness}")
    return request


def build_micro_artifact(spec: dict[str, Any]) -> dict[str, Any]:
    source_type = spec["source_type"]
    if source_type == "catalog":
        payload = load_case(spec["source_id"])
        return (
            payload["solve_bundle"]
            if spec["import_kind"] == "solve_bundle"
            else payload["scenario"]
        )
    if source_type == "scenario_file":
        return _read_json(
            ROOT / "data" / "examples" / f"{spec['source_id']}.json"
        )
    if source_type == "artifact":
        return _artifact_bundle(spec)
    raise ValueError(f"unsupported micro source type: {source_type!r}")


def _flight_option(
    option_id: str,
    flight: dict[str, Any],
    delay: int | None,
) -> dict[str, Any]:
    if delay is None:
        return {
            "option_id": option_id,
            "base_flight_id": flight["flight_id"],
            "operation_type": "cancel",
            "change_types": ["cancel"],
            "origin": None,
            "destination": None,
            "dep_time": None,
            "arr_time": None,
            "block_minutes": None,
            "departure_delay_minutes": None,
            "arrival_delay_minutes": None,
            "notes": "Synthetic cancellation candidate.",
        }
    dep = datetime.fromisoformat(flight["sched_dep"].replace("Z", "+00:00")) + timedelta(minutes=delay)
    arr = datetime.fromisoformat(flight["sched_arr"].replace("Z", "+00:00")) + timedelta(minutes=delay)
    return {
        "option_id": option_id,
        "base_flight_id": flight["flight_id"],
        "operation_type": "operate",
        "change_types": ["unchanged"] if delay == 0 else ["delay"],
        "origin": flight["origin"],
        "destination": flight["destination"],
        "dep_time": _iso(dep),
        "arr_time": _iso(arr),
        "block_minutes": flight["duration"],
        "departure_delay_minutes": delay,
        "arrival_delay_minutes": delay,
        "notes": "Synthetic unchanged candidate." if delay == 0 else f"Synthetic delay candidate: {delay} minutes.",
    }


def build_stress_bundle(profile: ScaleProfile) -> dict[str, Any]:
    if profile.profile_id == "P1-seconds":
        bundle = load_case("benchmark-disruption-recovery")["solve_bundle"]
        assert bundle is not None
        readiness = solve_readiness(bundle)
        if not readiness["solve_ready"]:
            raise ValueError(f"reference P1 bundle is not solve-ready: {readiness}")
        return bundle

    rng = random.Random(profile.seed)
    scenario_id = profile.profile_id.lower().replace("-", "_")
    day = datetime(2026, 10, 15, tzinfo=timezone.utc)
    recovery_start = day + timedelta(hours=7)
    recovery_end = day + timedelta(hours=18)
    hub = "H00"
    airport_ids = [hub] + [f"S{index:02d}" for index in range(1, profile.airport_count)]
    airports = [
        {
            "airport_id": airport_id,
            "name": "Synthetic Hub" if airport_id == hub else f"Synthetic Spoke {airport_id[1:]}",
        }
        for airport_id in airport_ids
    ]

    flights: list[dict[str, Any]] = []
    rotations: dict[str, list[str]] = {}
    tail_spokes: dict[str, tuple[str, str]] = {}
    flight_number = 1
    for tail_index in range(profile.operating_aircraft):
        tail_id = f"{profile.profile_id}_AC{tail_index + 1:03d}"
        crew_id = f"{profile.profile_id}_CR{tail_index + 1:03d}"
        spoke1 = airport_ids[1 + tail_index % (len(airport_ids) - 1)]
        spoke2 = airport_ids[1 + (tail_index * 3 + 1) % (len(airport_ids) - 1)]
        if spoke2 == spoke1:
            spoke2 = airport_ids[1 + (tail_index * 3 + 2) % (len(airport_ids) - 1)]
        tail_spokes[tail_id] = (spoke1, spoke2)
        offset = timedelta(minutes=(tail_index % 3) * 5)
        legs = (
            (hub, spoke1, day + timedelta(hours=8) + offset),
            (spoke1, hub, day + timedelta(hours=10) + offset),
            (hub, spoke2, day + timedelta(hours=12) + offset),
            (spoke2, hub, day + timedelta(hours=14) + offset),
        )
        rotations[tail_id] = []
        for leg_index, (origin, destination, dep) in enumerate(legs):
            flight_id = f"{profile.profile_id}_F{flight_number:04d}"
            flight_number += 1
            rotations[tail_id].append(flight_id)
            flights.append(
                {
                    "flight_id": flight_id,
                    "origin": origin,
                    "destination": destination,
                    "sched_dep": _iso(dep),
                    "sched_arr": _iso(dep + timedelta(minutes=60)),
                    "duration": 60,
                    "original_aircraft": tail_id,
                    "original_equipment": "E1",
                    "original_crew": crew_id,
                    "strategic_flag": leg_index == 2 and tail_index % 4 == 0,
                    "market_flag": leg_index == 0 and tail_index % 2 == 0,
                    "min_seats": 5 if leg_index == 0 and tail_index % 2 == 0 else 0,
                    "max_delay": max(profile.delay_minutes),
                }
            )

    aircraft = []
    crew = []
    for tail_index in range(profile.operating_aircraft):
        tail_id = f"{profile.profile_id}_AC{tail_index + 1:03d}"
        crew_id = f"{profile.profile_id}_CR{tail_index + 1:03d}"
        aircraft.append(
            {
                "tail_id": tail_id,
                "equipment_type": "E1",
                "initial_station_at_t": hub,
                "required_station_at_T_end": hub,
                "maintenance_required": tail_index == profile.operating_aircraft - 1,
                "maintenance_stations": [hub] if tail_index == profile.operating_aircraft - 1 else [],
                "original_rotation": rotations[tail_id],
            }
        )
        crew.append(
            {
                "crew_id": crew_id,
                "rating": "E1",
                "start_station_at_t": hub,
                "required_station_at_T_end": hub,
                "original_duties": [rotations[tail_id]],
                "original_pairing": rotations[tail_id],
            }
        )
    for reserve_index in range(profile.reserve_aircraft):
        aircraft.append(
            {
                "tail_id": f"{profile.profile_id}_RAC{reserve_index + 1:03d}",
                "equipment_type": "E1",
                "initial_station_at_t": hub,
                "required_station_at_T_end": hub,
                "maintenance_required": False,
                "maintenance_stations": [],
                "original_rotation": [],
            }
        )
    for reserve_index in range(profile.reserve_crew):
        crew.append(
            {
                "crew_id": f"{profile.profile_id}_RCR{reserve_index + 1:03d}",
                "rating": "E1",
                "start_station_at_t": hub,
                "required_station_at_T_end": hub,
                "original_duties": [],
                "original_pairing": [],
            }
        )

    capacity_cut = max(1, round(profile.operating_aircraft * profile.disrupted_fraction))
    airport_intervals: list[dict[str, Any]] = []
    cursor = recovery_start
    while cursor < recovery_end:
        interval_end = cursor + timedelta(minutes=30)
        for airport_id in airport_ids:
            dep_capacity = profile.flight_count + 20
            if airport_id == hub and cursor == day + timedelta(hours=8):
                dep_capacity = max(1, profile.operating_aircraft - capacity_cut)
            airport_intervals.append(
                {
                    "airport": airport_id,
                    "start_time": _iso(cursor),
                    "end_time": _iso(interval_end),
                    "arr_capacity": profile.flight_count + 20,
                    "dep_capacity": dep_capacity,
                    "gate_capacity": profile.aircraft_count + 20,
                    "curfew_flag": False,
                    "weather_restrictions": ["synthetic_capacity_reduction"]
                    if airport_id == hub and cursor == day + timedelta(hours=8)
                    else [],
                }
            )
        cursor = interval_end

    flight_by_id = {item["flight_id"]: item for item in flights}
    direct_routes = [[item["flight_id"]] for item in flights]
    connecting_routes: list[list[str]] = []
    for tail_index in range(profile.operating_aircraft):
        inbound = rotations[f"{profile.profile_id}_AC{tail_index + 1:03d}"][1]
        outbound_tail = (tail_index + 1) % profile.operating_aircraft
        outbound = rotations[f"{profile.profile_id}_AC{outbound_tail + 1:03d}"][2]
        if flight_by_id[inbound]["origin"] != flight_by_id[outbound]["destination"]:
            connecting_routes.append([inbound, outbound])
    if not connecting_routes:
        connecting_routes = direct_routes

    passenger_routes: list[list[str]] = []
    for group_index in range(profile.passenger_groups):
        if group_index % 5 == 0:
            passenger_routes.append(connecting_routes[group_index % len(connecting_routes)])
        else:
            passenger_routes.append(direct_routes[group_index % len(direct_routes)])

    passengers: list[dict[str, Any]] = []
    passenger_load_by_flight = {flight_id: 0 for flight_id in flight_by_id}
    group_counts: list[int] = []
    for group_index, route in enumerate(passenger_routes):
        first = flight_by_id[route[0]]
        last = flight_by_id[route[-1]]
        count = rng.randint(5, 20)
        group_counts.append(count)
        for flight_id in route:
            passenger_load_by_flight[flight_id] += count
        passengers.append(
            {
                "pax_group_id": f"{profile.profile_id}_P{group_index + 1:05d}",
                "count": count,
                "origin": first["origin"],
                "destination": last["destination"],
                "original_departure": first["sched_dep"],
                "scheduled_arrival": last["sched_arr"],
                "original_itinerary": route,
            }
        )

    scenario = {
        "scenario_id": scenario_id,
        "recovery_window": {
            "start_time": _iso(recovery_start),
            "end_time": _iso(recovery_end),
        },
        "airports": airports,
        "flights": flights,
        "aircraft": aircraft,
        "crew": crew,
        "passengers": passengers,
        "airport_intervals": airport_intervals,
        "disruptions": [
            {
                "airport": hub,
                "start_time": _iso(day + timedelta(hours=8)),
                "end_time": _iso(day + timedelta(hours=8, minutes=30)),
                "capacity_change": -capacity_cut,
                "restriction_type": "synthetic_departure_capacity_reduction",
            }
        ],
    }

    flight_options: list[dict[str, Any]] = []
    options_by_flight: dict[str, list[dict[str, Any]]] = {}
    for flight in flights:
        flight_id = flight["flight_id"]
        candidates = [
            _flight_option(f"{flight_id}_O", flight, 0),
            *[
                _flight_option(f"{flight_id}_D{delay}", flight, delay)
                for delay in profile.delay_minutes
            ],
            _flight_option(f"{flight_id}_C", flight, None),
        ]
        flight_options.extend(candidates)
        options_by_flight[flight_id] = [
            item for item in candidates if item["operation_type"] == "operate"
        ]

    passenger_itineraries: list[dict[str, Any]] = []
    for group_index, route in enumerate(passenger_routes):
        passenger = passengers[group_index]
        option_sets = [options_by_flight[flight_id] for flight_id in route]
        candidate_number = 1
        for combination in product(*option_sets):
            chronological = all(
                left["destination"] == right["origin"]
                and left["arr_time"] <= right["dep_time"]
                for left, right in zip(combination, combination[1:])
            )
            if not chronological:
                continue
            final = combination[-1]
            scheduled_arrival = datetime.fromisoformat(
                passenger["scheduled_arrival"].replace("Z", "+00:00")
            )
            actual_arrival = datetime.fromisoformat(final["arr_time"].replace("Z", "+00:00"))
            arrival_delay = max(0, int((actual_arrival - scheduled_arrival).total_seconds() // 60))
            passenger_itineraries.append(
                {
                    "itinerary_id": f"{passenger['pax_group_id']}_I{candidate_number:03d}",
                    "pax_group_id": passenger["pax_group_id"],
                    "status": "transported",
                    "segments": [
                        {
                            "segment_type": "flight",
                            "flight_option_id": option["option_id"],
                            "origin": None,
                            "destination": None,
                            "dep_time": None,
                            "arr_time": None,
                        }
                        for option in combination
                    ],
                    "final_destination": passenger["destination"],
                    "arrival_time": final["arr_time"],
                    "arrival_delay_minutes": arrival_delay,
                    "cost_components": {},
                    "notes": "Deterministically generated direct or connecting itinerary.",
                }
            )
            candidate_number += 1
        passenger_itineraries.append(
            {
                "itinerary_id": f"{passenger['pax_group_id']}_UNSERVED",
                "pax_group_id": passenger["pax_group_id"],
                "status": "unserved",
                "segments": [],
                "final_destination": None,
                "arrival_time": None,
                "arrival_delay_minutes": None,
                "cost_components": {},
                "notes": "Explicit unserved fallback.",
            }
        )

    columns = {
        "schema_version": "1.0.0",
        "scenario_id": scenario_id,
        "time_unit": "minute",
        "notes": [
            f"Generated deterministically from validation scale profile {profile.profile_id}.",
            "Aircraft strings and crew pairings are intentionally generated by the solver.",
        ],
        "flight_options": flight_options,
        "aircraft_strings": [],
        "crew_pairings": [],
        "passenger_itineraries": passenger_itineraries,
    }
    seat_capacity: dict[str, int] = {}
    for flight_index, flight in enumerate(flights):
        load = passenger_load_by_flight[flight["flight_id"]]
        for option in options_by_flight[flight["flight_id"]]:
            if option["departure_delay_minutes"] == 0 and flight_index % 7 == 0 and load:
                seat_capacity[option["option_id"]] = max(0, load - 1)
            else:
                seat_capacity[option["option_id"]] = load + 20
    capacity = {
        "schema_version": "1.0.0",
        "capacity_profile_id": f"{scenario_id}_capacity",
        "scenario_id": scenario_id,
        "source": "test_fixture",
        "units": "seats",
        "seat_capacity_by_option_id": seat_capacity,
        "notes": [
            "Synthetic residual capacity; every seventh original option is one seat short to activate PRM-C03."
        ],
    }
    request = SolveRequest(
        schema_version="1.0.0",
        scenario=scenario,
        recovery_columns=columns,
        capacity_profile=capacity,
        cost_profile_id="phase2_test_v1",
        cost_overrides={"passenger_delay_per_pax_minute": 1.0},
        algorithm=ALGORITHM,
        profile_ids=default_profile_ids(),
    ).model_dump(mode="json")

    Scenario.model_validate(scenario)
    RecoveryColumns.model_validate(columns)
    readiness = solve_readiness(request)
    if not readiness["solve_ready"]:
        raise ValueError(f"generated stress bundle is not solve-ready: {readiness}")
    return request


def _bundle_counts(bundle: dict[str, Any]) -> dict[str, int]:
    scenario = bundle["scenario"]
    columns = bundle["recovery_columns"]
    return {
        "airports": len(scenario["airports"]),
        "flights": len(scenario["flights"]),
        "aircraft": len(scenario["aircraft"]),
        "crew": len(scenario["crew"]),
        "passenger_groups": len(scenario["passengers"]),
        "airport_intervals": len(scenario["airport_intervals"]),
        "disruptions": len(scenario["disruptions"]),
        "flight_options": len(columns["flight_options"]),
        "passenger_itineraries": len(columns["passenger_itineraries"]),
    }


def generate_validation_suite(output_root: Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    micro_root = output_root / "frozen" / "micro"
    stress_root = output_root / "frozen" / "stress"
    manifest_entries: list[dict[str, Any]] = []
    expectations: dict[str, Any] = {}
    coverage: dict[str, list[str]] = {constraint_id: [] for constraint_id in CONSTRAINT_IDS}

    for spec in MICRO_CASES:
        artifact = build_micro_artifact(spec)
        path = micro_root / f"{spec['case_id']}.json"
        _write_json(path, artifact)
        for constraint_id in spec["constraints"]:
            coverage[constraint_id].append(spec["case_id"])
        expectations[spec["case_id"]] = spec["expected"]
        scenario = artifact["scenario"] if spec["import_kind"] == "solve_bundle" else artifact
        entry = {
            "case_id": spec["case_id"],
            "label": spec["label"],
            "category": spec["category"],
            "import_kind": spec["import_kind"],
            "relative_path": path.relative_to(output_root).as_posix(),
            "source_type": spec["source_type"],
            "source_id": spec["source_id"],
            "constraints": spec["constraints"],
            "algorithms": spec["algorithms"],
            "expected": spec["expected"],
            "human_check": spec["human_check"],
            "scenario_counts": {
                key: len(scenario.get(key, []))
                for key in (
                    "airports",
                    "flights",
                    "aircraft",
                    "crew",
                    "passengers",
                    "airport_intervals",
                    "disruptions",
                )
            },
            "sha256": _sha256(path),
        }
        manifest_entries.append(entry)

    profile_payload: list[dict[str, Any]] = []
    for profile in SCALE_PROFILES:
        bundle = build_stress_bundle(profile)
        path = stress_root / f"{profile.profile_id}.json"
        _write_json(path, bundle)
        profile_data = asdict(profile)
        profile_data["delay_minutes"] = list(profile.delay_minutes)
        profile_data["expected_counts"] = _bundle_counts(bundle)
        profile_payload.append(profile_data)
        manifest_entries.append(
            {
                "case_id": profile.profile_id,
                "label": profile.label,
                "category": "压力数据",
                "import_kind": "solve_bundle",
                "relative_path": path.relative_to(output_root).as_posix(),
                "target_runtime": profile.target_runtime,
                "calibration_status": profile.calibration_status,
                "seed": profile.seed,
                "counts": _bundle_counts(bundle),
                "sha256": _sha256(path),
            }
        )

    manifest = {
        "schema_version": "1.0.0",
        "generator": "backend.data_generation.validation_suite",
        "generator_version": "1.0.0",
        "semantics": {
            "runtime_targets_are_reference_machine_bands": True,
            "artificial_waits_allowed": False,
            "stress_profiles_require_calibration": True,
            "large_profiles_may_require_a_full_solver_license": True,
        },
        "entries": manifest_entries,
    }
    _write_json(output_root / "manifest.json", manifest)
    _write_json(output_root / "expectations.json", expectations)
    _write_json(output_root / "constraint_coverage.json", coverage)
    _write_json(output_root / "scale_profiles.json", profile_payload)
    _write_json(output_root / "calibration_results.json", CALIBRATION_RESULTS)

    readme_lines = [
        "# AIR 验证与压力数据套件",
        "",
        "本目录由 `python scripts/generate_validation_suite.py` 确定性生成。",
        "语义源由生成器和固定种子维护，`frozen/` 下的 JSON 是供当前 HTML 直接导入的适配产物。",
        "",
        "- `frozen/micro/`：20 个小规模、可解释案例；",
        "- `frozen/stress/`：P1–P5 五档压力数据；",
        "- `manifest.json`：导入类型、来源、规模、预期和 SHA-256；",
        "- `expectations.json`：机器可读预期；",
        "- `constraint_coverage.json`：20 项约束到案例的映射；",
        "- `scale_profiles.json`：压力生成参数与目标时间带。",
        "- `calibration_results.json`：参考机器的真实校准结果。",
        "",
        "## 导入",
        "",
        "`import_kind=scenario` 的文件使用 Scenario 导入入口；",
        "`import_kind=solve_bundle` 的文件使用完整求解包导入入口。",
        "HTML 契约变化后重新运行适配生成器即可，不应手工修改冻结文件。",
        "",
        "## 边界",
        "",
        "压力档的时间是参考机器目标带，不是跨机器承诺。P3–P5 通常需要完整求解器许可证；",
        "生成器不会加入人工等待。未完成实机标定前，`calibration_status` 保持 `uncalibrated`。",
    ]
    _write_text(output_root / "README.md", "\n".join(readme_lines))

    card_lines = ["# 微型案例人工验算卡", ""]
    for spec in MICRO_CASES:
        entry = next(item for item in manifest_entries if item["case_id"] == spec["case_id"])
        card_lines.extend(
            [
                f"## {spec['label']} (`{spec['case_id']}`)",
                "",
                f"- 导入方式：`{spec['import_kind']}`",
                f"- 类别：{spec['category']}",
                f"- 规模：{json.dumps(entry['scenario_counts'], ensure_ascii=False)}",
                f"- 重点约束：{', '.join(spec['constraints']) if spec['constraints'] else 'Scenario 结构/引用校验'}",
                f"- 算法机制：{', '.join(spec['algorithms'])}",
                f"- 预期：`{json.dumps(spec['expected'], ensure_ascii=False)}`",
                f"- 人工核验：{spec['human_check']}",
                "",
            ]
        )
    _write_text(output_root / "MICRO_CASE_CARDS.md", "\n".join(card_lines))

    coverage_lines = [
        "# 约束覆盖矩阵",
        "",
        "| 约束 ID | 覆盖案例 |",
        "|---|---|",
    ]
    coverage_lines.extend(
        f"| `{constraint_id}` | {', '.join(f'`{case_id}`' for case_id in case_ids)} |"
        for constraint_id, case_ids in coverage.items()
    )
    _write_text(output_root / "CONSTRAINT_COVERAGE.md", "\n".join(coverage_lines))

    stress_lines = [
        "# 压力档与校准规则",
        "",
        "| 档位 | 目标时间 | 机场 | 航班 | 飞机 | 机组 | 旅客组 | 航班候选 | 旅客行程 | 状态 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for profile_data in profile_payload:
        counts = profile_data["expected_counts"]
        stress_lines.append(
            f"| {profile_data['profile_id']} | {profile_data['target_runtime']} | "
            f"{counts['airports']} | {counts['flights']} | {counts['aircraft']} | "
            f"{counts['crew']} | {counts['passenger_groups']} | {counts['flight_options']} | "
            f"{counts['passenger_itineraries']} | {profile_data['calibration_status']} |"
        )
    stress_lines.extend(
        [
            "",
            "## 校准方法",
            "",
            "1. 固定机器、求解器版本、许可证和并发环境；",
            "2. P1–P3 预热后运行三次，取中位数；P4 运行两次，P5 至少完成一次长时运行；",
            "3. 记录 wall time、峰值内存、上下界、Gap、主问题轮次、访问计划数、列数和分支节点；",
            "4. 若未进入目标时间带，先调耦合度、候选密度和资源可互换性，再调实体数量；",
            "5. 不以 sleep 或前端动画制造运行时间；",
            "6. P4–P5 可按预算终止，但必须保留有效状态、incumbent、bound、Gap 和终止原因。",
            "",
            "## 当前实测",
            "",
            "- P1：本机 1.308 秒达到最优，目标 18080，审计通过；",
            "- P2：70.074 秒预算后受控终止，LB=120、UB=600；它是压力终止样例，不是已完成最优演示；",
            "- P3–P5：本次未执行长时校准，继续标记为未校准。",
        ]
    )
    _write_text(output_root / "STRESS_PROFILES.md", "\n".join(stress_lines))
    return manifest
