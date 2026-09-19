from __future__ import annotations

from common.adapters import ADAPTER_SPECS, get_adapter


def test_six_architectures_have_distinct_framework_contracts() -> None:
    assert set(ADAPTER_SPECS) == {f"T{i}" for i in range(1, 7)}
    assert get_adapter("T1").interaction_mode == "one_shot"
    assert get_adapter("T2").framework == "langgraph"
    assert get_adapter("T3").interaction_mode == "codeact"
    assert get_adapter("T4").mounting_mode == "native_skills"
    assert get_adapter("T4").framework_version == "1.49.2"
    assert get_adapter("T5").interaction_mode == "sequential"
    assert get_adapter("T5").framework_version == "1.15.22"
    assert get_adapter("T6").native_runtime is True
