"""Nơi bộ nạp ghi ra (DESIGN.md §5.5).

Sink tách khỏi pipeline vì **một lý do thực tế**: máy dev chưa cài PostgreSQL
(§9.3), mà vòng đọc → ánh xạ → ghi là phần dễ sai nhất và cần test ngay. Với
một Protocol ở giữa, `runner.py` không biết nó đang ghi vào đâu, nên cùng một
đường mã chạy được trên cả hai sink và test chạy trên CPU.

Hai bản hiện thực:

* ``JsonlSink`` — ghi mỗi bảng thành một file JSONL. Đây là sink mặc định khi
  chưa có Postgres, và là sink của test. Nó **không** phải một database: nó
  không kiểm được CHECK, trigger hay quyền, nên nó không thay được nghiệm thu
  M1. Nó chỉ chứng minh pipeline đọc và ánh xạ đúng.
* ``PostgresSink`` — bản thật. Nó cần `psycopg`, chưa có trong workspace, nên
  khởi tạo nó báo đúng thiếu gì và cần làm gì, thay vì đổ một
  `ModuleNotFoundError`.

**Mọi bảng có khoá tự nhiên**, kể cả bảng append-only, vì đó là điều kiện để
`fwsync import` chạy lại từ đầu cho cùng kết quả (§5.5). Cron chạy 5 phút một
lần trên cùng artifact của lõi; không có khoá thì không phân biệt được "dòng
này đã nạp" với "dòng mới".

Hai cách ghi, khác nhau đúng ở chỗ có được sửa hay không:

* Bảng thường: **upsert**. Gặp lại khoá thì cập nhật dòng cũ.
* Bảng `APPEND_ONLY`: **chèn nếu chưa có, không bao giờ sửa**. Gặp lại khoá
  thì bỏ qua và đếm là `unchanged`. Append-only nghĩa là không UPDATE một dòng
  đã ghi (R4, 03 §4.4); nó không có nghĩa là chèn lại cùng một artifact.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

#: Khoá tự nhiên của từng bảng, để upsert thay vì chèn trùng. Khoá này là của
#: lõi, không phải UUID web tự sinh: nạp lại cùng artifact phải trúng đúng
#: dòng cũ.
NATURAL_KEY: dict[str, tuple[str, ...]] = {
    "sources": ("source_ref",),
    "datasets": ("dataset_code",),
    "episodes": ("episode_ref",),
    "releases": ("release_ref",),
    "release_items": ("release_ref", "episode_ref"),
    "run_plans": ("run_plan_ref",),
    "experiments": ("experiment_code",),
    "model_checkpoints": ("checkpoint_ref",),
    "training_metrics": ("experiment_code", "attempt", "step", "split"),
    "probe_results": ("probe", "checkpoint_ref"),
    "sim_evaluations": ("evaluation_ref",),
    "eval_episodes": ("eval_episode_ref",),
    "flywheel_recommendations": ("recommendation_ref",),
    "system_diagnoses": ("eval_episode_ref", "config_sha256"),
    "failure_clusters": ("cluster_ref",),
    "interventions": ("intervention_ref",),
    "decisions": ("decision_ref",),
    "cost_ledger_entries": ("entry_ref",),
    "price_books": ("name", "sha256"),
    "defect_manifests": ("manifest_ref",),
    "defect_items": ("manifest_ref", "target_ref", "code"),
    "defect_bench_groups": ("result_sha256", "group_name"),
    "defect_scores": ("result_sha256", "group_name", "layer", "metric", "subject"),
    "pipeline_stage_runs": ("dataset_code", "stage_number", "attempt_no"),
    "experiment_datasets": ("experiment_code", "release_ref"),
    "diagnostic_runs": ("cluster_ref", "step_no", "check_name"),
    "repair_tickets": ("cluster_ref", "diagnosis"),
    "flywheel_algo_steps": ("recommendation_ref", "step_no", "cluster_ref", "eval_episode_ref"),
    # Bốn bảng append-only dưới cũng cần khoá: nó là danh tính của một lần
    # đo, để nạp lại cùng lần đo không thành lần đo thứ hai.
    "episode_qa_reports": ("report_ref",),
    "train_diagnoses": (
        "experiment_code", "checkpoint_ref", "config_sha256", "code",
        "start_step", "group_name", "dim",
    ),
    "train_diagnosis_skips": ("experiment_code", "config_sha256", "code"),
    "fix_rate_events": ("cluster_ref", "intervention_ref"),
}

#: Bảng chỉ được thêm (luật R4, 03 §4.4, trigger C8): chèn nếu chưa có,
#: **không bao giờ sửa** dòng đã ghi. Hai lần chấm là hai số đo vì chúng có
#: hai khoá khác nhau (`report_ref` khác, `config_sha256` khác), không phải vì
#: cùng một artifact được nạp hai lần. `cost_ledger_entries` và
#: `defect_scores` thuộc nhóm này: trước đây chúng được upsert, tức là nạp lại
#: một bút toán sẽ UPDATE nó, đúng điều R4 cấm.
APPEND_ONLY: frozenset[str] = frozenset(
    {
        "episode_qa_reports",
        "train_diagnoses",
        "train_diagnosis_skips",
        "fix_rate_events",
        "cost_ledger_entries",
        "defect_bench_groups",
        "defect_scores",
    }
)


@dataclass
class WriteCounts:
    """Đếm theo bảng, đúng hình dạng `sync_runs.counts`."""

    inserted: int = 0
    updated: int = 0
    rejected: int = 0
    # Dòng append-only đã có từ lần nạp trước, bỏ qua không sửa. Tách khỏi
    # `updated` vì một bút toán sổ chi phí bị "updated" là một vi phạm R4,
    # còn "unchanged" là đúng.
    unchanged: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "inserted": self.inserted,
            "updated": self.updated,
            "rejected": self.rejected,
            "unchanged": self.unchanged,
        }


class Sink(Protocol):
    """Chỗ bộ nạp ghi dòng ra. `runner.py` chỉ biết Protocol này."""

    def write(self, table: str, row: dict[str, Any]) -> str:
        """Ghi một dòng; trả `"inserted"` hoặc `"updated"`."""
        ...

    def counts(self) -> dict[str, dict[str, int]]:
        """Số đếm theo bảng, để ghi vào `sync_runs.counts`."""
        ...

    def commit(self) -> None:
        """Chốt lần ghi. `JsonlSink` ghi file ở đây."""
        ...


@dataclass
class JsonlSink:
    """Ghi mỗi bảng thành một file JSONL dưới `directory`.

    Giữ dòng trong bộ nhớ tới `commit()` vì upsert cần tra khoá tự nhiên, và
    đọc lại file sau mỗi dòng sẽ chậm bậc hai. Bộ nạp mỗi lần chạy xử lý vài
    nghìn dòng nên giữ hết trong bộ nhớ là đủ.
    """

    directory: Path
    rows: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))
    _counts: dict[str, WriteCounts] = field(default_factory=lambda: defaultdict(WriteCounts))

    def __post_init__(self) -> None:
        """Đọc lại dòng đã ghi lần trước, nếu thư mục đã có.

        Cần thiết để số đếm **trung thực**. Không đọc lại thì mỗi tiến trình
        bắt đầu rỗng, nên lần nạp thứ hai báo `inserted` trong khi Postgres sẽ
        báo `updated` — và `sync_runs.counts` của hai sink sẽ kể hai câu
        chuyện khác nhau về cùng một lần nạp. Nội dung file vẫn như nhau cả
        hai cách; chỉ con số là sai.
        """
        if not self.directory.is_dir():
            return
        for path in sorted(self.directory.glob("*.jsonl")):
            table = path.stem
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.rows[table].append(json.loads(line))

    def write(self, table: str, row: dict[str, Any]) -> str:
        key = NATURAL_KEY.get(table)
        if key is None:
            # `test_every_table_the_loader_writes_has_a_natural_key` chặn
            # chuyện này ở CI; ở đây chỉ để không mất dữ liệu nếu nó lọt.
            self.rows[table].append(row)
            self._counts[table].inserted += 1
            return "inserted"
        existing = self._find(table, key, row)
        if existing is None:
            self.rows[table].append(row)
            self._counts[table].inserted += 1
            return "inserted"
        if table in APPEND_ONLY:
            self._counts[table].unchanged += 1
            return "unchanged"
        existing.update(row)
        self._counts[table].updated += 1
        return "updated"

    def reject(self, table: str) -> None:
        self._counts[table].rejected += 1

    def counts(self) -> dict[str, dict[str, int]]:
        return {table: count.as_dict() for table, count in sorted(self._counts.items())}

    def commit(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        for table, rows in sorted(self.rows.items()):
            path = self.directory / f"{table}.jsonl"
            path.write_text(
                "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in rows),
                encoding="utf-8",
                newline="\n",
            )

    def _find(
        self, table: str, key: tuple[str, ...], row: dict[str, Any]
    ) -> dict[str, Any] | None:
        if any(name not in row for name in key):
            # Khoá tự nhiên thiếu thì không tra được; thêm dòng mới và để
            # CHECK của Postgres bắt nếu nó thật sự trùng.
            return None
        wanted = tuple(row[name] for name in key)
        for candidate in self.rows[table]:
            if tuple(candidate.get(name) for name in key) == wanted:
                return candidate
        return None


@dataclass
class PostgresSink:
    """Bản thật. Chưa dùng được: `psycopg` không có trong workspace.

    Không `import psycopg` ở đầu file để `fwsync` vẫn chạy được với
    `JsonlSink` trên máy chưa cài gì. Khởi tạo nó báo đúng thiếu gì.
    """

    dsn: str

    def __post_init__(self) -> None:
        raise NotImplementedError(
            "PostgresSink chưa dựng. Cần: (1) PostgreSQL 16 trên máy, "
            "(2) `psycopg` trong workspace, (3) quyết định W8 về ADR-13 "
            "(03 §2.4 xếp web và DB server vào hàng hoãn tới L1+). "
            "Tới lúc đó dùng `--sink jsonl`, xem web/README.md"
        )

    def write(self, table: str, row: dict[str, Any]) -> str:  # pragma: no cover
        raise NotImplementedError

    def counts(self) -> dict[str, dict[str, int]]:  # pragma: no cover
        raise NotImplementedError

    def commit(self) -> None:  # pragma: no cover
        raise NotImplementedError
