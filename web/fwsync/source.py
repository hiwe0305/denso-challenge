"""Đọc một thư mục artifact của lõi (DESIGN.md §3.2, §5.5).

Tầng này chỉ biến file thành dòng JSON đã phân loại. Nó không validate theo
hợp đồng (việc của `mapping.py`) và không ghi gì (việc của `sink.py`).

**Tên file quyết định loại artifact**, theo một bảng khai báo. Lõi ghi catalog
thành `catalog/<bảng>/part-<ulid>.jsonl` và bộ mock ghi `<bảng>.jsonl`, nên
suy từ tên là đủ và không cần đoán nội dung. Một file không có trong bảng thì
**bỏ qua kèm log**, không làm đổ cả lần nạp: lõi còn thêm artifact mới sau
này, và một file lạ không phải lý do để dừng (§9.4, "bộ nạp khoan dung").

**Hai mức khoan dung, khác nhau có chủ ý:**

* Bảng có model hợp đồng (`episodes`, `episode_qa_reports`, `training_metrics`,
  `train_diagnoses`, `probe_results`, `defect_manifests`) đi qua
  `mapping.py` và bị **từ chối** nếu sai schema. Đây là phần hợp đồng đã chốt,
  nên sai là lỗi thật.
* Bảng chưa có file schema (`Source`, `Condition`, `Release`, `Checkpoint`,
  `RunPlan`, `Score`, `Cluster`, `FixRateEvent`, `LedgerEntry`, `Decision` —
  đều nằm ở S1-10 #36, chưa merge) đi qua đường khoan dung: cột lạ bị bỏ kèm
  log, cột thiếu để None. Phụ lục B nói rõ phải như vậy cho tới khi #36 merge.
  Chuyển một bảng sang đường nghiêm là xoá một dòng ở `TOLERANT_TABLES`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Tên file (không đuôi) → bảng đích. Khoá cũng là tên bảng catalog của lõi,
#: nên một file `catalog/episodes/part-01.jsonl` và một file `episodes.jsonl`
#: của bộ mock vào cùng một chỗ.
FILE_TO_TABLE: dict[str, str] = {
    "sources": "sources",
    "datasets": "datasets",
    "episodes": "episodes",
    "pipeline_stage_runs": "pipeline_stage_runs",
    "stage_runs": "pipeline_stage_runs",
    "qa_reports": "episode_qa_reports",
    "episode_qa_reports": "episode_qa_reports",
    "releases": "releases",
    "release_items": "release_items",
    "run_plans": "run_plans",
    "experiments": "experiments",
    "experiment_datasets": "experiment_datasets",
    "checkpoints": "model_checkpoints",
    "model_checkpoints": "model_checkpoints",
    "training_metrics": "training_metrics",
    "train_diagnoses": "train_diagnoses",
    "probes": "probe_results",
    "probe_results": "probe_results",
    "evaluations": "sim_evaluations",
    "sim_evaluations": "sim_evaluations",
    "eval_episodes": "eval_episodes",
    "system_diagnoses": "system_diagnoses",
    "recommendation": "flywheel_recommendations",
    "recommendations": "flywheel_recommendations",
    "failure_clusters": "failure_clusters",
    "diagnostic_runs": "diagnostic_runs",
    "interventions": "interventions",
    "fix_rate_events": "fix_rate_events",
    "repair_tickets": "repair_tickets",
    "flywheel_algo_steps": "flywheel_algo_steps",
    "decisions": "decisions",
    "ledger": "cost_ledger_entries",
    "cost_ledger_entries": "cost_ledger_entries",
    "price_books": "price_books",
    "defect_manifest": "defect_manifests",
    "defect_manifests": "defect_manifests",
    "defect_scores": "defect_scores",
}

#: Bảng đi qua đường khoan dung vì thực thể của nó chưa có file schema trong
#: `flywheel-contracts` (S1-10 #36). Xoá một dòng ở đây khi #36 merge và bảng
#: đó có model, để nó chuyển sang đường nghiêm.
TOLERANT_TABLES: frozenset[str] = frozenset(
    {
        "sources",
        "datasets",
        "pipeline_stage_runs",
        "releases",
        "release_items",
        "run_plans",
        "experiments",
        "experiment_datasets",
        "model_checkpoints",
        "sim_evaluations",
        "eval_episodes",
        "system_diagnoses",
        "flywheel_recommendations",
        "failure_clusters",
        "diagnostic_runs",
        "interventions",
        "fix_rate_events",
        "repair_tickets",
        "flywheel_algo_steps",
        "decisions",
        "cost_ledger_entries",
        "price_books",
        "defect_scores",
    }
)


class SourceError(ValueError):
    """Một file nguồn không đọc được."""


@dataclass(frozen=True)
class Record:
    """Một dòng artifact, kèm chỗ nó đến từ để báo lỗi nói được file và dòng."""

    table: str
    payload: Any
    path: Path
    line: int | None = None

    @property
    def where(self) -> str:
        return f"{self.path.name}" if self.line is None else f"{self.path.name}:{self.line}"


@dataclass
class SourceScan:
    """Kết quả quét một thư mục nguồn."""

    records: list[Record] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)

    def by_table(self, table: str) -> list[Record]:
        return [record for record in self.records if record.table == table]

    @property
    def tables(self) -> list[str]:
        return sorted({record.table for record in self.records})


def table_of(path: Path) -> str | None:
    """Bảng đích của một file, hoặc None nếu không nhận ra.

    Lõi ghi `catalog/<bảng>/part-<ulid>.jsonl`, nên tên thư mục cha được thử
    trước tên file: một file `part-01.jsonl` chỉ nói được nó thuộc bảng nào
    qua thư mục.
    """
    if path.parent.name in FILE_TO_TABLE:
        return FILE_TO_TABLE[path.parent.name]
    return FILE_TO_TABLE.get(path.stem)


def scan(directory: Path) -> SourceScan:
    """Đọc mọi file `.json` và `.jsonl` dưới một thư mục, kể cả thư mục con."""
    if not directory.is_dir():
        raise SourceError(f"`{directory}` không phải thư mục")
    result = SourceScan()
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix not in (".json", ".jsonl"):
            continue
        table = table_of(path)
        if table is None:
            # Lõi còn thêm artifact mới; một file lạ không phải lý do để dừng.
            result.ignored.append(str(path.relative_to(directory)))
            continue
        result.records.extend(_read(path, table))
    return result


def _read(path: Path, table: str) -> Iterator[Record]:
    if path.suffix == ".jsonl":
        yield from _read_jsonl(path, table)
    else:
        yield from _read_json(path, table)


def _read_jsonl(path: Path, table: str) -> Iterator[Record]:
    for number, line in enumerate(_text(path).splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise SourceError(f"`{path.name}` dòng {number} không phải JSON: {error}") from error
        yield Record(table=table, payload=payload, path=path, line=number)


def _read_json(path: Path, table: str) -> Iterator[Record]:
    try:
        payload = json.loads(_text(path))
    except json.JSONDecodeError as error:
        raise SourceError(f"`{path.name}` không phải JSON: {error}") from error
    # Một file `.json` có thể là một đối tượng hoặc một danh sách đối tượng.
    if isinstance(payload, list):
        for index, item in enumerate(payload):
            yield Record(table=table, payload=item, path=path, line=index + 1)
    else:
        yield Record(table=table, payload=payload, path=path)


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SourceError(f"`{path}` không đọc được: {error}") from error


def tolerant_row(
    payload: Any, allowed: frozenset[str], where: str
) -> tuple[dict[str, Any], list[str]]:
    """Một dòng của bảng chưa có model hợp đồng, cộng danh sách cột lạ đã bỏ.

    Trả về cột lạ chứ không im lặng: Phụ lục B đòi khoan dung, nhưng khoan
    dung mà không ghi lại thì không ai biết lõi đã thêm trường gì, và trường
    đó sẽ nằm ngoài web cho tới khi có người tình cờ phát hiện.
    """
    if not isinstance(payload, dict):
        raise SourceError(f"{where}: phải là một đối tượng JSON, gặp {type(payload).__name__}")
    row = {key: value for key, value in payload.items() if key in allowed}
    unknown = sorted(key for key in payload if key not in allowed)
    return row, unknown
