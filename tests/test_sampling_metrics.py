from logmask_drain.metrics import (
    grouping_accuracy_exact,
    normalize_generic_template,
    parsing_accuracy_generic,
    parsing_accuracy_typed,
    variable_span_f1,
)
from logmask_drain.models import VariableSpan
from logmask_drain.sampling import sample_lines


def test_entropy_greedy_samples_and_fills():
    lines = [f"same token {i}" for i in range(10)]
    sampled = sample_lines(lines, k=5, mode="entropy_greedy", jaccard_threshold=0.0)

    assert len(sampled) == 5


def test_pa_generic_normalization():
    predicted = ["User <VAR:ID> logged in from <VAR:IP>"]
    truth = ["User <*> logged in from <*>"]

    assert normalize_generic_template(predicted[0]) == truth[0]
    assert parsing_accuracy_generic(predicted, truth) == 1.0


def test_pa_typed_requires_exact_typed_placeholders():
    predicted = [
        "User <VAR:USERNAME> logged in from <VAR:IP>",
        "User <VAR:ID> logged out",
    ]
    truth = [
        "User <VAR:ID> logged in from <VAR:IP>",
        "User <VAR:ID> logged out",
    ]

    assert parsing_accuracy_generic(predicted, truth) == 1.0
    assert parsing_accuracy_typed(predicted, truth) == 0.5


def test_ga_exact_uses_cluster_set_equality():
    predicted = ["A", "A", "C", "B"]
    truth = ["A", "A", "A", "B"]

    assert grouping_accuracy_exact(predicted, truth) == 0.25


def test_variable_span_f1_exact_boundaries_and_types():
    predicted = [
        [
            {"type": "ID", "start": 5, "end": 10},
            {"type": "IP", "start": 20, "end": 29},
        ],
        [VariableSpan(type="PID", value="1234", start=4, end=8, mask_name="pid")],
    ]
    truth = [
        [
            {"type": "USERNAME", "start": 5, "end": 10},
            {"type": "IP", "start": 20, "end": 29},
        ],
        [{"type": "PID", "start": 4, "end": 8}],
    ]

    typed = variable_span_f1(predicted, truth, typed=True)
    untyped = variable_span_f1(predicted, truth, typed=False)

    assert typed["true_positive"] == 2
    assert typed["precision"] == 2 / 3
    assert typed["recall"] == 2 / 3
    assert typed["f1"] == 2 / 3
    assert untyped["f1"] == 1.0


def test_variable_span_f1_empty_inputs_are_perfect():
    result = variable_span_f1([[]], [[]])

    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["f1"] == 1.0
