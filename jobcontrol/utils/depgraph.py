"""
Dependency graph exploration / resolution functions.

The dependency graph is represented as a dictionary of
``{<vertex>: [<dependencies>]}``.
"""


class DepResolutionError(Exception):
    pass


class DepLoop(DepResolutionError):
    pass


def resolve_deps(graph, start, with_weights=False):
    distances = {}
    distances[start] = 0

    def _dfs_explore(vertex, trail):
        for dest in graph[vertex]:
            if dest in trail:
                raise DepLoop('Loop detected! {0!r} -> {1!r}'
                              .format(trail, dest))

            if dest not in distances:
                distances[dest] = len(trail)
            else:
                distances[dest] = max(len(trail), distances[dest])

            _dfs_explore(dest, trail + [dest])

    _dfs_explore(start, [start])

    items = [(y, x) for (x, y) in distances.iteritems()]
    items.sort()
    items.reverse()

    if with_weights:
        return items

    return [x[1] for x in items]
