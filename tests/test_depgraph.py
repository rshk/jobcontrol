import pytest

from jobcontrol.utils.depgraph import resolve_deps, DepLoop


def test_graph_resolution():
    assert resolve_deps({
        'A': ['B', 'C'],
        'B': [],
        'C': [],
    }, 'A') == ['C', 'B', 'A']

    assert resolve_deps({
        'A': ['B', 'D'],
        'B': ['C'],
        'C': ['D'],
        'D': [],
    }, 'A') == ['D', 'C', 'B', 'A']

    with pytest.raises(DepLoop):
        resolve_deps({
            'A': ['B', 'D'],
            'B': ['C'],
            'C': ['D'],
            'D': ['B'],
        }, 'A')

    assert resolve_deps({
        'A': ['B', 'E'],
        'B': [],
        'C': ['B'],
        'D': ['C'],
        'E': ['D'],
    }, 'A') == ['B', 'C', 'D', 'E', 'A']
