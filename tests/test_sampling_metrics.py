from logmask_drain.metrics import grouping_accuracy_exact, normalize_generic_template, parsing_accuracy_generic
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


def test_ga_exact_uses_cluster_set_equality():
    predicted = ["A", "A", "C", "B"]
    truth = ["A", "A", "A", "B"]

    assert grouping_accuracy_exact(predicted, truth) == 0.25
