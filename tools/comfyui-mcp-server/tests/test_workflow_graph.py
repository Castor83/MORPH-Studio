"""Tests for workflow graph validation and per-run overrides."""

import pytest

from workflow_tools import WorkflowError, apply_overrides, validate_api_workflow


def api_graph():
    """A minimal API-format workflow: flat, keyed by node id."""
    return {
        "6": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 20}},
        "105:111": {"class_type": "PrimitiveFloat", "inputs": {"value": 5.0}},
    }


# ---------------------------------------------------------------------------
# Format validation
# ---------------------------------------------------------------------------

def test_ui_format_workflow_is_rejected():
    ui_graph = {"nodes": [{"id": 6, "type": "KSampler"}], "links": []}

    with pytest.raises(WorkflowError) as exc:
        validate_api_workflow(ui_graph, "C:/wf/my_workflow.json")

    message = str(exc.value)
    assert "UI-format" in message
    assert "Export (API)" in message
    assert "C:/wf/my_workflow.json" in message


def test_api_format_workflow_is_accepted():
    validate_api_workflow(api_graph(), "C:/wf/my_workflow.json")


def test_non_dict_workflow_is_rejected():
    with pytest.raises(WorkflowError):
        validate_api_workflow([1, 2, 3], "C:/wf/my_workflow.json")


def test_node_without_class_type_is_rejected():
    graph = {"6": {"inputs": {"seed": 1}}}

    with pytest.raises(WorkflowError) as exc:
        validate_api_workflow(graph, "C:/wf/my_workflow.json")

    assert "class_type" in str(exc.value)


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------

def test_override_replaces_an_input_value():
    graph = apply_overrides(api_graph(), {"6.seed": 42})

    assert graph["6"]["inputs"]["seed"] == 42
    assert graph["6"]["inputs"]["steps"] == 20, "unrelated inputs must be untouched"


def test_override_key_splits_on_last_dot_so_colon_node_ids_work():
    """Node ids like '105:111' are common in exported subgraphs."""
    graph = apply_overrides(api_graph(), {"105:111.value": 8.0})

    assert graph["105:111"]["inputs"]["value"] == 8.0


def test_unknown_node_id_raises_and_names_valid_ids():
    with pytest.raises(WorkflowError) as exc:
        apply_overrides(api_graph(), {"999.seed": 1})

    message = str(exc.value)
    assert "999" in message
    assert "105:111" in message, "the error should list the node ids that do exist"


def test_unknown_input_name_raises_and_names_valid_inputs():
    with pytest.raises(WorkflowError) as exc:
        apply_overrides(api_graph(), {"6.stpes": 1})

    message = str(exc.value)
    assert "stpes" in message
    assert "steps" in message, "the error should list the inputs that do exist"


def test_override_key_without_a_dot_is_rejected():
    with pytest.raises(WorkflowError) as exc:
        apply_overrides(api_graph(), {"seed": 1})

    assert "node_id.input_name" in str(exc.value)


def test_overrides_do_not_mutate_the_caller_graph():
    original = api_graph()
    apply_overrides(original, {"6.seed": 42})

    assert original["6"]["inputs"]["seed"] == 1
