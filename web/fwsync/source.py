"""Đọc một thư mục artifact của lõi (DESIGN.md §3.2, §5.5).

Tầng này chỉ biến file thành dòng JSON đã phân loại. Nó không validate theo
hợp đồng (việc của `mapping.py`) và không ghi gì (việc của `sink.py`).

**Tên file quyết định loại artifact**, theo một bảng khai báo. Lõi ghi catalog
thành `catalog/<bảng>/part-<ulid>.jsonl` và bộ mock ghi `<bảng>.jsonl`, nên
suy từ tên là đủ và không cần đoán nội dung. Một file không có trong bảng thì
**bỏ qua kèm log**, không làm đổ cả lần nạp: lõi còn thêm artifact mới sau
này, và một file lạ không phải lý do để dừng (§9.4, "bộ nạp khoan dung").

**Hai mức khoan dung, khác nhau có chủ ý:**

* Artifact có hình dạng hợp đồng đi qua `mapping.py` và bị **từ chối** nếu
  sai schema. Đó là `episodes`, `episode_qa_reports`, `training_metrics`,
  `train_diagnoses`, `probe_results`, `defect_manifests`, `bench_result.json`
  của DA-31, và mọi thứ lõi ghi theo bố cục store của nó: catalog
  `catalog/<bảng số ít>/part-<ulid>.jsonl` (`CORE_CATALOG`, khớp
  `flywheel.store.views.CATALOG_TABLES`) và sổ chi phí
  `runs/<run_plan>/<job>/ledger.jsonl`. Model hợp đồng của chín thực thể S1-10
  đã merge, nên sai là lỗi thật (review #72 điểm 1).
* Bộ mock ghi các bảng đó bằng **dòng web** (`sources.jsonl`,
  `decisions.jsonl`, `ledger.jsonl`…, tên số nhiều, khoá `*_ref`). Chúng đi
  đường khoan dung: cột lạ bị bỏ kèm log, cột thiếu để None. Bố cục quyết định
  đường đi, không phải nội dung, nên một dòng mock không bao giờ bị đọc như
  hợp đồng và ngược lại.

**Một dòng hỏng không làm đổ cả lần nạp** (review #72 điểm 6). Dòng JSONL
không đọc được vào `SourceScan.errors` rồi quét tiếp. Dòng cuối không có
`\\n` mà cũng không phải JSON là dòng lõi đang ghi dở: nó bị bỏ kèm log, như
`flywheel.store.tables.complete_lines`, và lần nạp sau sẽ đọc nó.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
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
    # DA-31 ghi `<out>/bench_result.json`; một file cho cả hai bảng của lần
    # chấm (bản 0.6). `defect_scores.jsonl` dạng tp/fp/fn cũ không còn nhận.
    "bench_result": "defect_bench_groups",
}

#: Artifact mà tên file một mình không nói được bảng: khoá là cặp (thư mục
#: cha, tên file không đuôi). Làn DA-13 ghi `<store>/diagnosis/system.jsonl`
#: (`SYSTEM_RECORDS` của `diagnosis/system/artifact.py`); khoá `system` trần
#: thì bắt nhầm mọi `system.jsonl` khác, nên khoá đúng là cả cặp (W13).
#:
#: Bản ghi đến từ đây mang hình dạng **hợp đồng**, không phải dòng web, nên
#: đi đường nghiêm (`Record.contract`) dù bảng đích nằm trong
#: `TOLERANT_TABLES` vì các dòng của bộ mock.
CONTRACT_PATHS: dict[tuple[str, str], str] = {
    ("diagnosis", "system"): "system_diagnoses",
}

#: Thư mục catalog của lõi → bảng web. Lõi đặt tên bảng **số ít**
#: (`flywheel.store.views.CATALOG_TABLES`) và ghi bằng model hợp đồng, nên mọi
#: dòng dưới `catalog/<tên>/` đi đường nghiêm. `None`: lõi có bảng đó nhưng web
#: chưa có chỗ chứa; file được liệt kê trong `ignored` kèm lý do, không im lặng.
CORE_CATALOG: dict[str, str | None] = {
    "source": "sources",
    "release": "releases",
    "checkpoint": "model_checkpoints",
    "run_plan": "run_plans",
    "cluster": "failure_clusters",
    "fix_rate_event": "fix_rate_events",
    "decision": "decisions",
    "episode": "episodes",
    "qa_report": "episode_qa_reports",
    # `Score` theo episode chưa có bảng web: `eval_episodes` dựng từ lượt eval,
    # và eval thật hiện chưa ghi Score vào store.
    "score": None,
    # Điều kiện ban đầu chưa có màn nào đọc.
    "condition": None,
}

#: Lý do một bảng catalog của lõi chưa nạp, cho dòng `ignored`.
NOT_LOADED_YET = "lõi có bảng này nhưng web chưa có bảng chứa nó"

#: Thư mục chứa sổ chi phí của lõi: `runs/<run_plan>/<job>/ledger*.jsonl`
#: (`flywheel.store.ledger_append`). Sổ không nằm trong catalog.
CORE_LEDGER_DIR = "runs"

#: Bảng có dòng mock đi đường khoan dung. Dòng của chính lõi cho các bảng này
#: (catalog, sổ chi phí, `diagnosis/system.jsonl`) vẫn đi đường nghiêm, vì
#: `Record.contract` được đặt theo bố cục.
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
    #: Đến từ một đường của `CONTRACT_PATHS`: hình dạng là hợp đồng, đi đường
    #: nghiêm, kể cả khi bảng đích có dòng mock đi đường khoan dung.
    contract: bool = False

    @property
    def where(self) -> str:
        return f"{self.path.name}" if self.line is None else f"{self.path.name}:{self.line}"


@dataclass
class SourceScan:
    """Kết quả quét một thư mục nguồn."""

    records: list[Record] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    #: Dòng hoặc file không đọc được, hình dạng `sync_runs.errors`. Quét vẫn
    #: chạy tiếp các dòng khác.
    errors: list[dict[str, Any]] = field(default_factory=list)

    def by_table(self, table: str) -> list[Record]:
        return [record for record in self.records if record.table == table]

    @property
    def tables(self) -> list[str]:
        return sorted({record.table for record in self.records})


def table_of(path: Path) -> str | None:
    """Bảng đích của một file, hoặc None nếu không nhận ra.

    Lõi ghi `catalog/<bảng>/part-<ulid>.jsonl`, nên tên thư mục cha được thử
    trước tên file: một file `part-01.jsonl` chỉ nói được nó thuộc bảng nào
    qua thư mục. Truyền đường dẫn **tương đối** với thư mục nguồn, như `scan`.
    """
    return _classify(path)[0]


def _classify(path: Path) -> tuple[str | None, bool, str | None]:
    """(bảng đích, có phải đường hợp đồng không, lý do bỏ) của một file.

    `path` tương đối với thư mục nguồn, để một thư mục `runs` nằm **trên**
    thư mục nguồn không biến mọi file thành sổ chi phí. Thứ tự thử đi từ cụ
    thể tới chung: cặp (thư mục, tên) của `CONTRACT_PATHS`, catalog của lõi,
    sổ chi phí của lõi, rồi tên thư mục, rồi tên file.
    """
    pair = (path.parent.name, path.stem)
    if pair in CONTRACT_PATHS:
        return CONTRACT_PATHS[pair], True, None
    if path.parent.parent.name == "catalog" and path.parent.name in CORE_CATALOG:
        table = CORE_CATALOG[path.parent.name]
        return table, True, None if table else NOT_LOADED_YET
    if (
        CORE_LEDGER_DIR in path.parts[:-1]
        and path.stem.startswith("ledger")
        and path.suffix == ".jsonl"
    ):
        return "cost_ledger_entries", True, None
    if path.parent.name in FILE_TO_TABLE:
        return FILE_TO_TABLE[path.parent.name], False, None
    return FILE_TO_TABLE.get(path.stem), False, None


def scan(directory: Path) -> SourceScan:
    """Đọc mọi file `.json` và `.jsonl` dưới một thư mục, kể cả thư mục con.

    Chỉ một thư mục không tồn tại mới làm hàm này ném lỗi: đó là cấu hình
    sai, không phải dữ liệu sai. File hay dòng không đọc được vào `errors`.
    """
    if not directory.is_dir():
        raise SourceError(f"`{directory}` không phải thư mục")
    result = SourceScan()
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix not in (".json", ".jsonl"):
            continue
        relative = path.relative_to(directory)
        table, contract, note = _classify(relative)
        if table is None:
            # Lõi còn thêm artifact mới; một file lạ không phải lý do để dừng.
            result.ignored.append(f"{relative}: {note}" if note else str(relative))
            continue
        try:
            text = _text(path)
        except SourceError as error:
            result.errors.append(_unreadable(table, path.name, error))
            continue
        records = (
            _read_jsonl(path, table, text, result)
            if path.suffix == ".jsonl"
            else _read_json(path, table, text, result)
        )
        result.records.extend(
            replace(record, contract=contract) if contract else record for record in records
        )
    return result


def _unreadable(table: str, where: str, error: Exception) -> dict[str, Any]:
    return {"table": table, "ref": where, "code": "SourceError", "message": str(error)}


def _read_jsonl(path: Path, table: str, text: str, scan: SourceScan) -> list[Record]:
    records: list[Record] = []
    lines = text.split("\n")
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            if number == len(lines):
                # Không có `\n` ở cuối và không phải JSON: lõi đang ghi dở dòng
                # này. Lần nạp sau đọc lại nó; ghi vào `ignored` để thấy được.
                scan.ignored.append(f"{path.name}:{number}: dòng cuối đang ghi dở, bỏ qua")
                continue
            scan.errors.append(
                _unreadable(table, f"{path.name}:{number}",
                            SourceError(f"`{path.name}` dòng {number} không phải JSON: {error}"))
            )
            continue
        records.append(Record(table=table, payload=payload, path=path, line=number))
    return records


def _read_json(path: Path, table: str, text: str, scan: SourceScan) -> list[Record]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        scan.errors.append(
            _unreadable(table, path.name, SourceError(f"`{path.name}` không phải JSON: {error}"))
        )
        return []
    # Một file `.json` có thể là một đối tượng hoặc một danh sách đối tượng.
    if isinstance(payload, list):
        return [
            Record(table=table, payload=item, path=path, line=index + 1)
            for index, item in enumerate(payload)
        ]
    return [Record(table=table, payload=payload, path=path)]


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
