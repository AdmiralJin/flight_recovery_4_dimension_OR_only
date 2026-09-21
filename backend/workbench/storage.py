from __future__ import annotations

import gzip
import hashlib
import json
import os
import sqlite3
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from backend.schemas.workbench import (
    CompilePreview,
    DraftDocument,
    DraftPayload,
    DraftSummary,
    JobStatus,
    RunEvent,
    RunRecord,
    RuntimeProfile,
    RuntimeProfileParameters,
    SnapshotRecord,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_ROOT = ROOT / ".workbench"


class WorkbenchNotFoundError(KeyError):
    pass


class WorkbenchConflictError(ValueError):
    pass


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repository_state() -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout
        diff = subprocess.run(
            ["git", "diff", "--binary", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            timeout=5,
        ).stdout
        return {
            "git_commit": commit,
            "dirty": bool(status.strip()),
            "diff_hash": hashlib.sha256(diff + status.encode("utf-8")).hexdigest(),
        }
    except (OSError, subprocess.SubprocessError):
        return {"git_commit": None, "dirty": None, "diff_hash": None}


class WorkbenchStore:
    def __init__(self, state_root: Path = DEFAULT_STATE_ROOT) -> None:
        self.state_root = state_root.resolve()
        self.artifact_root = self.state_root / "artifacts"
        self.database_path = self.state_root / "workbench.sqlite3"
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS workbench_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                INSERT OR IGNORE INTO workbench_meta(key, value)
                VALUES ('schema_version', '1');

                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_hash TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS drafts (
                    draft_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source_case_id TEXT,
                    working_hash TEXT NOT NULL,
                    working_artifact_hash TEXT NOT NULL REFERENCES artifacts(artifact_hash),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS draft_revisions (
                    revision_id TEXT PRIMARY KEY,
                    draft_id TEXT NOT NULL REFERENCES drafts(draft_id) ON DELETE CASCADE,
                    revision_number INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    artifact_hash TEXT NOT NULL REFERENCES artifacts(artifact_hash),
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(draft_id, revision_number)
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    draft_id TEXT NOT NULL REFERENCES drafts(draft_id) ON DELETE CASCADE,
                    revision_id TEXT NOT NULL REFERENCES draft_revisions(revision_id),
                    content_hash TEXT NOT NULL,
                    artifact_hash TEXT NOT NULL REFERENCES artifacts(artifact_hash),
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
                    draft_id TEXT NOT NULL REFERENCES drafts(draft_id),
                    input_hash TEXT NOT NULL,
                    job_status TEXT NOT NULL,
                    optimization_status TEXT,
                    trace_level TEXT NOT NULL,
                    runtime_profile_id TEXT NOT NULL DEFAULT 'default-exact',
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    result_artifact_hash TEXT REFERENCES artifacts(artifact_hash),
                    error_json TEXT
                );

                CREATE TABLE IF NOT EXISTS run_events (
                    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                    seq INTEGER NOT NULL,
                    emitted_at TEXT NOT NULL,
                    elapsed_seconds REAL NOT NULL,
                    stage TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY(run_id, seq)
                );

                CREATE INDEX IF NOT EXISTS idx_draft_revisions_draft
                ON draft_revisions(draft_id, revision_number DESC);
                CREATE INDEX IF NOT EXISTS idx_snapshots_draft
                ON snapshots(draft_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_runs_status_created
                ON runs(job_status, created_at);
                CREATE INDEX IF NOT EXISTS idx_runs_draft_created
                ON runs(draft_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS runtime_profiles (
                    profile_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    base_profile_id TEXT,
                    parameters_json TEXT NOT NULL,
                    builtin INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            run_columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(runs)").fetchall()
            }
            if "runtime_profile_id" not in run_columns:
                connection.execute(
                    "ALTER TABLE runs ADD COLUMN runtime_profile_id TEXT NOT NULL DEFAULT 'default-exact'"
                )
            now = _now()
            connection.execute(
                """
                INSERT OR IGNORE INTO runtime_profiles(
                    profile_id, name, base_profile_id, parameters_json,
                    builtin, created_at, updated_at
                ) VALUES ('default-exact', 'Default exact', NULL, '{}', 1, ?, ?)
                """,
                (now, now),
            )
            connection.execute("PRAGMA optimize")

    def put_artifact(self, kind: str, value: Any) -> str:
        payload = canonical_json_bytes(value)
        digest = hashlib.sha256(payload).hexdigest()
        relative = Path(digest[:2]) / f"{digest}.json.gz"
        target = self.artifact_root / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary_path: str | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=target.parent,
                    prefix=f".{digest}.",
                    suffix=".tmp",
                    delete=False,
                ) as raw:
                    temporary_path = raw.name
                    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
                        compressed.write(payload)
                    raw.flush()
                    os.fsync(raw.fileno())
                os.replace(temporary_path, target)
            finally:
                if temporary_path and os.path.exists(temporary_path):
                    os.unlink(temporary_path)
        with self.connection() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO artifacts(
                    artifact_hash, kind, relative_path, size_bytes, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (digest, kind, relative.as_posix(), target.stat().st_size, _now()),
            )
        return digest

    def get_artifact(self, digest: str) -> Any:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT relative_path FROM artifacts WHERE artifact_hash = ?",
                (digest,),
            ).fetchone()
        if row is None:
            raise WorkbenchNotFoundError(f"unknown artifact: {digest}")
        path = self.artifact_root / row["relative_path"]
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)

    def create_draft(self, document: DraftDocument) -> DraftPayload:
        data = document.model_dump(mode="json")
        digest = self.put_artifact("draft_working_copy", data)
        draft_id = str(uuid4())
        now = _now()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO drafts(
                    draft_id, name, source_case_id, working_hash,
                    working_artifact_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft_id,
                    document.name,
                    document.source_case_id,
                    digest,
                    digest,
                    now,
                    now,
                ),
            )
        return self.get_draft(draft_id)

    def list_drafts(self) -> list[DraftSummary]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT d.*, COUNT(r.revision_id) AS revision_count
                FROM drafts d
                LEFT JOIN draft_revisions r ON r.draft_id = d.draft_id
                GROUP BY d.draft_id
                ORDER BY d.updated_at DESC
                """
            ).fetchall()
        return [self._draft_summary(row) for row in rows]

    def get_draft(self, draft_id: str) -> DraftPayload:
        with self.connection() as connection:
            row = connection.execute(
                """
                SELECT d.*, COUNT(r.revision_id) AS revision_count
                FROM drafts d
                LEFT JOIN draft_revisions r ON r.draft_id = d.draft_id
                WHERE d.draft_id = ?
                GROUP BY d.draft_id
                """,
                (draft_id,),
            ).fetchone()
        if row is None:
            raise WorkbenchNotFoundError(f"unknown draft: {draft_id}")
        document = DraftDocument.model_validate(
            self.get_artifact(row["working_artifact_hash"])
        )
        return DraftPayload(**self._draft_summary(row).model_dump(), document=document)

    def update_draft(
        self, draft_id: str, base_hash: str, document: DraftDocument
    ) -> DraftPayload:
        data = document.model_dump(mode="json")
        digest = self.put_artifact("draft_working_copy", data)
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE drafts
                SET name = ?, source_case_id = ?, working_hash = ?,
                    working_artifact_hash = ?, updated_at = ?
                WHERE draft_id = ? AND working_hash = ?
                """,
                (
                    document.name,
                    document.source_case_id,
                    digest,
                    digest,
                    _now(),
                    draft_id,
                    base_hash,
                ),
            )
            if cursor.rowcount != 1:
                exists = connection.execute(
                    "SELECT 1 FROM drafts WHERE draft_id = ?", (draft_id,)
                ).fetchone()
                if exists is None:
                    raise WorkbenchNotFoundError(f"unknown draft: {draft_id}")
                raise WorkbenchConflictError("draft hash changed; reload before saving")
        return self.get_draft(draft_id)

    def create_revision(self, draft_id: str, base_hash: str, note: str = "") -> str:
        draft = self.get_draft(draft_id)
        if draft.working_hash != base_hash:
            raise WorkbenchConflictError("draft hash changed; reload before versioning")
        revision_id = str(uuid4())
        with self.connection() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(revision_number), 0) AS value FROM draft_revisions WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()
            revision_number = int(row["value"]) + 1
            artifact_hash = connection.execute(
                "SELECT working_artifact_hash FROM drafts WHERE draft_id = ?",
                (draft_id,),
            ).fetchone()["working_artifact_hash"]
            connection.execute(
                """
                INSERT INTO draft_revisions(
                    revision_id, draft_id, revision_number, content_hash,
                    artifact_hash, note, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_id,
                    draft_id,
                    revision_number,
                    draft.working_hash,
                    artifact_hash,
                    note,
                    _now(),
                ),
            )
        return revision_id

    def create_snapshot(
        self,
        draft_id: str,
        base_hash: str,
        compile_preview: CompilePreview,
        note: str = "",
    ) -> SnapshotRecord:
        if not compile_preview.valid or compile_preview.solve_request is None:
            raise WorkbenchConflictError("cannot snapshot an invalid compile preview")
        if compile_preview.draft_hash != base_hash:
            raise WorkbenchConflictError("compile preview does not match current draft")
        revision_id = self.create_revision(draft_id, base_hash, note)
        snapshot_id = str(uuid4())
        created_at = _now()
        payload = {
            "schema_version": "2.0.0",
            "snapshot_id": snapshot_id,
            "draft_id": draft_id,
            "revision_id": revision_id,
            "content_hash": compile_preview.compiled_hash,
            "created_at": created_at,
            "solve_request": compile_preview.solve_request,
            "compile_preview": compile_preview.model_dump(mode="json"),
            "draft_document": self.get_draft(draft_id).document.model_dump(mode="json"),
            "environment": _repository_state(),
        }
        artifact_hash = self.put_artifact("solve_snapshot", payload)
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO snapshots(
                    snapshot_id, draft_id, revision_id, content_hash,
                    artifact_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    draft_id,
                    revision_id,
                    compile_preview.compiled_hash,
                    artifact_hash,
                    created_at,
                ),
            )
        return SnapshotRecord.model_validate(payload)

    def get_snapshot(self, snapshot_id: str) -> SnapshotRecord:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT artifact_hash FROM snapshots WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            raise WorkbenchNotFoundError(f"unknown snapshot: {snapshot_id}")
        return SnapshotRecord.model_validate(self.get_artifact(row["artifact_hash"]))

    def create_run(
        self,
        snapshot: SnapshotRecord,
        trace_level: str,
        runtime_profile_id: str = "default-exact",
    ) -> RunRecord:
        self.get_runtime_profile(runtime_profile_id)
        run_id = str(uuid4())
        now = _now()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO runs(
                    run_id, snapshot_id, draft_id, input_hash, job_status,
                    trace_level, runtime_profile_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    snapshot.snapshot_id,
                    snapshot.draft_id,
                    snapshot.content_hash,
                    JobStatus.QUEUED.value,
                    trace_level,
                    runtime_profile_id,
                    now,
                ),
            )
        return self.get_run(run_id)

    def list_runs(self, draft_id: str | None = None) -> list[RunRecord]:
        query = "SELECT * FROM runs"
        params: tuple[Any, ...] = ()
        if draft_id:
            query += " WHERE draft_id = ?"
            params = (draft_id,)
        query += " ORDER BY created_at DESC"
        with self.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._run_record(row) for row in rows]

    def next_queued_run(self) -> RunRecord | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE job_status = ? ORDER BY created_at LIMIT 1",
                (JobStatus.QUEUED.value,),
            ).fetchone()
        return self._run_record(row) if row else None

    def get_run(self, run_id: str) -> RunRecord:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise WorkbenchNotFoundError(f"unknown run: {run_id}")
        return self._run_record(row)

    def update_run_status(
        self,
        run_id: str,
        status: JobStatus,
        *,
        optimization_status: str | None = None,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> RunRecord:
        result_hash = self.put_artifact("run_result", result) if result is not None else None
        fields = ["job_status = ?"]
        values: list[Any] = [status.value]
        if status in {JobStatus.PREPARING, JobStatus.RUNNING}:
            fields.append("started_at = COALESCE(started_at, ?)")
            values.append(_now())
        if status in {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.INTERRUPTED,
        }:
            fields.append("finished_at = ?")
            values.append(_now())
        if optimization_status is not None:
            fields.append("optimization_status = ?")
            values.append(optimization_status)
        if result_hash is not None:
            fields.append("result_artifact_hash = ?")
            values.append(result_hash)
        if error is not None:
            fields.append("error_json = ?")
            values.append(json.dumps(error, ensure_ascii=False, sort_keys=True))
        values.append(run_id)
        with self.connection() as connection:
            cursor = connection.execute(
                f"UPDATE runs SET {', '.join(fields)} WHERE run_id = ?",
                values,
            )
            if cursor.rowcount != 1:
                raise WorkbenchNotFoundError(f"unknown run: {run_id}")
        return self.get_run(run_id)

    def request_cancel(self, run_id: str) -> RunRecord:
        with self.connection() as connection:
            cursor = connection.execute(
                "UPDATE runs SET cancel_requested = 1 WHERE run_id = ?",
                (run_id,),
            )
            if cursor.rowcount != 1:
                raise WorkbenchNotFoundError(f"unknown run: {run_id}")
        return self.get_run(run_id)

    def append_event(self, event: RunEvent) -> RunEvent:
        data = event.model_dump(mode="json")
        payload = {
            key: value
            for key, value in data.items()
            if key
            not in {
                "run_id",
                "seq",
                "emitted_at",
                "elapsed_seconds",
                "stage",
                "event_type",
            }
        }
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO run_events(
                    run_id, seq, emitted_at, elapsed_seconds, stage,
                    event_type, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.run_id,
                    event.seq,
                    event.emitted_at.isoformat(),
                    event.elapsed_seconds,
                    event.stage,
                    event.event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                ),
            )
        return event

    def next_event_sequence(self, run_id: str) -> int:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(seq), 0) AS value FROM run_events WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return int(row["value"]) + 1

    def list_events(self, run_id: str, after: int = 0) -> list[RunEvent]:
        self.get_run(run_id)
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM run_events WHERE run_id = ? AND seq > ? ORDER BY seq",
                (run_id, after),
            ).fetchall()
        events: list[RunEvent] = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            events.append(
                RunEvent(
                    run_id=row["run_id"],
                    seq=row["seq"],
                    emitted_at=row["emitted_at"],
                    elapsed_seconds=row["elapsed_seconds"],
                    stage=row["stage"],
                    event_type=row["event_type"],
                    **payload,
                )
            )
        return events

    def mark_running_interrupted(self) -> int:
        with self.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE runs
                SET job_status = ?, finished_at = ?,
                    error_json = ?
                WHERE job_status IN (?, ?)
                """,
                (
                    JobStatus.INTERRUPTED.value,
                    _now(),
                    json.dumps(
                        {
                            "code": "worker_interrupted",
                            "message": "The local service restarted while the run was active.",
                            "retryable": True,
                        },
                        sort_keys=True,
                    ),
                    JobStatus.PREPARING.value,
                    JobStatus.RUNNING.value,
                ),
            )
            return cursor.rowcount

    def list_runtime_profiles(self) -> list[RuntimeProfile]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM runtime_profiles ORDER BY builtin DESC, name"
            ).fetchall()
        return [self._runtime_profile(row) for row in rows]

    def get_runtime_profile(self, profile_id: str) -> RuntimeProfile:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_profiles WHERE profile_id = ?", (profile_id,)
            ).fetchone()
        if row is None:
            raise WorkbenchNotFoundError(f"unknown runtime profile: {profile_id}")
        return self._runtime_profile(row)

    def clone_runtime_profile(
        self, base_profile_id: str, profile_id: str, name: str
    ) -> RuntimeProfile:
        base = self.get_runtime_profile(base_profile_id)
        now = _now()
        try:
            with self.connection() as connection:
                connection.execute(
                    """
                    INSERT INTO runtime_profiles(
                        profile_id, name, base_profile_id, parameters_json,
                        builtin, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        profile_id,
                        name,
                        base.profile_id,
                        json.dumps(base.parameters.model_dump(mode="json"), sort_keys=True),
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise WorkbenchConflictError(f"runtime profile already exists: {profile_id}") from exc
        return self.get_runtime_profile(profile_id)

    def update_runtime_profile(
        self, profile_id: str, name: str, parameters: RuntimeProfileParameters
    ) -> RuntimeProfile:
        profile = self.get_runtime_profile(profile_id)
        if profile.builtin:
            raise WorkbenchConflictError("built-in runtime profiles are read-only; clone first")
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE runtime_profiles
                SET name = ?, parameters_json = ?, updated_at = ?
                WHERE profile_id = ?
                """,
                (
                    name,
                    json.dumps(parameters.model_dump(mode="json"), sort_keys=True),
                    _now(),
                    profile_id,
                ),
            )
        return self.get_runtime_profile(profile_id)

    @staticmethod
    def _draft_summary(row: sqlite3.Row) -> DraftSummary:
        return DraftSummary(
            draft_id=row["draft_id"],
            name=row["name"],
            source_case_id=row["source_case_id"],
            working_hash=row["working_hash"],
            revision_count=int(row["revision_count"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _run_record(self, row: sqlite3.Row) -> RunRecord:
        result = (
            self.get_artifact(row["result_artifact_hash"])
            if row["result_artifact_hash"]
            else None
        )
        return RunRecord(
            run_id=row["run_id"],
            snapshot_id=row["snapshot_id"],
            draft_id=row["draft_id"],
            input_hash=row["input_hash"],
            job_status=row["job_status"],
            optimization_status=row["optimization_status"],
            trace_level=row["trace_level"],
            runtime_profile_id=row["runtime_profile_id"],
            cancel_requested=bool(row["cancel_requested"]),
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            result=result,
            error=json.loads(row["error_json"]) if row["error_json"] else None,
        )

    @staticmethod
    def _runtime_profile(row: sqlite3.Row) -> RuntimeProfile:
        return RuntimeProfile(
            profile_id=row["profile_id"],
            name=row["name"],
            base_profile_id=row["base_profile_id"],
            parameters=RuntimeProfileParameters.model_validate(
                json.loads(row["parameters_json"])
            ),
            builtin=bool(row["builtin"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


@lru_cache(maxsize=1)
def get_workbench_store() -> WorkbenchStore:
    return WorkbenchStore()
