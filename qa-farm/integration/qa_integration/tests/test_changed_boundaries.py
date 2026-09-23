"""Proves the changed_boundaries L0 primitive (plan T1.2)."""
from qa_integration.primitives.changed_boundaries import changed_boundaries

BOUNDARY_MAP = {"boundary_a": ["service_a/handler.py"], "boundary_b": ["service_b/handler.py"]}


def test_direct_boundary_change_included_docs_excluded():
    out = changed_boundaries(["service_a/handler.py", "README.md"], BOUNDARY_MAP)
    assert out == ["boundary_a"]


def test_reverse_dependency_closure_pulls_dependents():
    graph = {"boundary_c": ["boundary_a"]}      # boundary_c depends on boundary_a
    out = changed_boundaries(["service_a/handler.py"], BOUNDARY_MAP, boundary_graph=graph)
    assert "boundary_a" in out and "boundary_c" in out
    assert "boundary_b" not in out


def test_non_boundary_paths_filtered_to_empty():
    assert changed_boundaries(["docs/x.md", "assets/img.png"], BOUNDARY_MAP) == []
