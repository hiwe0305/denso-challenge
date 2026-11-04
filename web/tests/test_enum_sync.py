"""Mốc M0: enum của web khớp hợp đồng (DESIGN.md luật R3, nghiệm thu M0).

Test này là cách duy nhất phát hiện web lệch khỏi lõi mà không ai thấy. Một PR
hợp đồng đổi một giá trị enum sẽ làm nó đỏ, thay vì để FE hiện một nhãn không
còn tồn tại hoặc bỏ qua một giá trị mới.

Nó kiểm **hai nguồn khác nhau**, vì lõi khai enum ở hai chỗ:

* File JSON Schema trong ``packages/flywheel-contracts/schemas/``, là thứ FE
  sinh type từ đó.
* ``Literal`` trong mã ``flywheel.contracts``, là thứ API validate bằng.

Bộ nào ở nhóm ``SPEC`` thì **không** kiểm được: spec và design là văn bản.
Với chúng, test chỉ bắt được lỗi hình thức (trùng giá trị, bộ rỗng) và bắt
buộc mỗi bộ phải khai mình lấy từ mục nào — thiếu dòng nguồn là test đỏ, vì
một bộ giá trị không ai truy được nguồn là một bộ không ai dám sửa.
"""

from __future__ import annotations

import json
import typing
from pathlib import Path

import pytest

from web.contracts.enums import (
    ALL,
    CONTRACT,
    LITERAL_SOURCE,
    MULTI_FILE_SOURCE,
    SCHEMA_SOURCE,
    SPEC,
    SPEC_SOURCE,
    WEB,
    failure_codes,
    group_of,
)

SCHEMAS = (
    Path(__file__).resolve().parents[2] / "packages" / "flywheel-contracts" / "schemas"
)


def _at(doc: object, path: str) -> object:
    """Đi theo đường dẫn kiểu ``properties.kind`` hay ``a.anyOf[0]``."""
    node = doc
    for part in path.split("."):
        name, _, index = part.partition("[")
        node = node[name]  # type: ignore[index]
        if index:
            node = node[int(index.rstrip("]"))]  # type: ignore[index]
    return node


def _schema_enum(file_name: str, path: str) -> tuple[str, ...]:
    doc = json.loads((SCHEMAS / file_name).read_text(encoding="utf-8"))
    node = _at(doc, path)
    assert isinstance(node, dict), f"{file_name}:{path} không phải một node schema"
    values = node.get("enum") or ([node["const"]] if "const" in node else None)
    assert values is not None, f"{file_name}:{path} không khai `enum` hay `const`"
    return tuple(values)


def _literal_values(dotted: str) -> tuple[str, ...]:
    module_name, _, attribute = dotted.partition(".")
    module = __import__(f"flywheel.contracts.{module_name}", fromlist=[attribute])
    return tuple(typing.get_args(getattr(module, attribute)))


@pytest.mark.parametrize("name", sorted(SCHEMA_SOURCE))
def test_a_contract_enum_matches_its_json_schema(name: str) -> None:
    file_name, path = SCHEMA_SOURCE[name]
    assert CONTRACT[name] == _schema_enum(file_name, path), (
        f"bộ `{name}` lệch khỏi {file_name}:{path}. Đây là lỗi hợp đồng, không "
        f"phải lỗi web: sửa `web/contracts/enums.py` theo schema, đừng sửa schema"
    )


@pytest.mark.parametrize("name", sorted(LITERAL_SOURCE))
def test_a_contract_enum_matches_its_literal_in_code(name: str) -> None:
    assert CONTRACT[name] == _literal_values(LITERAL_SOURCE[name]), (
        f"bộ `{name}` lệch khỏi `flywheel.contracts.{LITERAL_SOURCE[name]}`"
    )


@pytest.mark.parametrize("name", sorted(MULTI_FILE_SOURCE))
def test_a_contract_enum_ghep_tu_nhieu_file_matches_each_const(name: str) -> None:
    from_files = tuple(
        _schema_enum(file_name, path)[0] for file_name, path in MULTI_FILE_SOURCE[name]
    )
    assert CONTRACT[name] == from_files


def test_every_contract_set_names_its_source() -> None:
    # Một bộ ở nhóm `contract` mà không khai nguồn thì không có gì kiểm nó, và
    # nó lặng lẽ thành một bộ do web tự đặt.
    declared = set(SCHEMA_SOURCE) | set(LITERAL_SOURCE) | set(MULTI_FILE_SOURCE)
    assert set(CONTRACT) == declared, (
        f"thiếu nguồn cho {sorted(set(CONTRACT) - declared)}; "
        f"khai thừa cho {sorted(declared - set(CONTRACT))}"
    )


def test_every_spec_set_names_the_document_section_it_came_from() -> None:
    assert set(SPEC) == set(SPEC_SOURCE), (
        f"thiếu dòng nguồn cho {sorted(set(SPEC) - set(SPEC_SOURCE))}"
    )
    assert all(SPEC_SOURCE[name].strip() for name in SPEC)


@pytest.mark.parametrize("name", sorted(ALL))
def test_no_set_is_empty_or_repeats_a_value(name: str) -> None:
    values = ALL[name]
    assert values, f"bộ `{name}` rỗng"
    assert len(set(values)) == len(values), f"bộ `{name}` trùng giá trị"


def test_the_three_groups_do_not_overlap() -> None:
    # Một tên nằm ở hai nhóm nghĩa là hai mức bảo đảm cho cùng một thứ, và
    # `group_of` sẽ trả về nhóm đầu tiên nó gặp.
    names = [set(CONTRACT), set(SPEC), set(WEB)]
    assert sum(len(group) for group in names) == len(set().union(*names))
    assert len(ALL) == sum(len(group) for group in names)


def test_group_of_says_which_guarantee_a_set_carries() -> None:
    assert group_of("data_class") == "contract"
    assert group_of("step_status") == "spec"
    assert group_of("sync_status") == "web"
    with pytest.raises(KeyError):
        group_of("khong_co_bo_nay")


def test_the_data_budget_diagnoses_are_three_of_the_eleven() -> None:
    # BR-07: chỉ ba chẩn đoán được tiêu ngân sách dữ liệu. Nếu bộ con này lạc
    # khỏi bộ 11 thì cột sinh `consumes_data_budget` so với một giá trị không
    # tồn tại và luôn ra FALSE.
    assert set(SPEC["data_budget_diagnosis"]) < set(SPEC["cluster_diagnosis"])
    assert len(SPEC["data_budget_diagnosis"]) == 3


def test_every_system_diagnosis_maps_to_a_cluster_diagnosis_or_is_excluded() -> None:
    # Bảng ánh xạ của DESIGN.md §4.4b. `clean` và `infra` cố ý không có dòng
    # bên cụm: một đi tiếp sang bước 5, một bị loại khỏi mẫu số.
    mapping = {
        "controller": "HE_THONG_CONTROLLER",
        "runtime": "HE_THONG_RUNTIME",
        "sync": "HE_THONG_DONG_BO",
        "calibration": "HE_THONG_CALIBRATION",
        "unknown": "CHUA_RO",
    }
    excluded = {"clean", "infra"}
    assert set(mapping) | excluded == set(SPEC["system_diagnosis"])
    assert set(mapping.values()) <= set(SPEC["cluster_diagnosis"])


def test_step_status_is_the_four_strings_the_scorer_ships() -> None:
    # DA-36 đã merge với đúng bốn chuỗi này. Test đọc thẳng enum của làn, nên
    # nếu scorer đổi giá trị thì web biết ngay thay vì lệch âm thầm.
    from flywheel.eval.scorer.status import StepStatus

    assert SPEC["step_status"] == tuple(status.value for status in StepStatus)


#: Hai test dưới đọc thẳng enum kiểm hệ thống của DA-13 (PR #71, đã merge).


def test_the_system_diagnoses_are_the_ones_da13_ships() -> None:
    from flywheel.eval.diagnosis.system.verdict import Diagnosis

    assert set(SPEC["system_diagnosis"]) == {item.value for item in Diagnosis}


def test_the_system_fault_codes_are_the_ones_da13_checks() -> None:
    from flywheel.eval.diagnosis.system.verdict import SYSTEM_CODES

    assert set(SPEC["system_fault_code"]) == set(SYSTEM_CODES)


def test_failure_codes_are_asked_per_task_not_merged() -> None:
    assert failure_codes("two_table") == SPEC["failure_code_two_table"]
    assert failure_codes("tray") == SPEC["failure_code_tray"]
    # Hai bộ trùng nhau một phần, nên một bộ gộp sẽ cho phép chấm một episode
    # task khay bằng mã của task hai bàn.
    shared = set(SPEC["failure_code_two_table"]) & set(SPEC["failure_code_tray"])
    assert shared == {"L-TIMEOUT", "L-BALANCE"}
    with pytest.raises(KeyError):
        failure_codes("khong_co_task")
