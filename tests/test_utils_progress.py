"""
Tests for all the utilities related to progress reporting (tree-style, ..)
"""

from jobcontrol.utils import ProgressReport


def test_progress_report_build_simple_tree():
    data = [
        (None, 1, 10, 'Doing stuff on ROOT'),
        (('1',), 2, 10, 'Doing stuff on 1'),
        (('1', '11'), 3, 10, 'Doing stuff on 1.1'),
        (('1', '12'), 4, 10, 'Doing stuff on 1.2'),
        (('2',), 5, 10, 'Doing stuff on 2'),
        (('2', '21'), 6, 10, 'Doing stuff on 2.1'),
        (('2', '22'), 7, 10, 'Doing stuff on 2.2'),
    ]

    report = ProgressReport.from_table(data)

    assert report.name is None
    assert report.current == 1
    assert report.total == 10
    assert report.status_line == 'Doing stuff on ROOT'

    assert len(report.children) == 2

    assert report.children[0].name == '1'
    assert report.children[0].current == 2
    assert report.children[0].total == 10
    assert report.children[0].status_line == 'Doing stuff on 1'

    assert len(report.children[0].children) == 2
    report.children[0].children[0].name == '11'
    report.children[0].children[1].name == '12'

    assert len(report.children[0].children[0].children) == 0
    assert len(report.children[0].children[1].children) == 0

    assert report.children[1].name == '2'
    assert report.children[1].current == 5
    assert report.children[1].total == 10
    assert report.children[1].status_line == 'Doing stuff on 2'

    assert len(report.children[1].children) == 2

    assert len(report.children[0].children) == 2
    report.children[0].children[0].name == '21'
    report.children[0].children[1].name == '22'

    assert len(report.children[1].children[0].children) == 0
    assert len(report.children[1].children[1].children) == 0


def test_progress_report_with_implicit_toplevels():
    data = [
        (('one', 'one-sub-1'), 1, 10, 'Doing stuff'),
        (('one', 'one-sub-2'), 2, 10, 'Doing stuff'),
        (('two', 'two-sub-1'), 4, 10, 'Doing stuff'),
        (('two', 'two-sub-2'), 8, 10, 'Doing stuff'),
    ]

    report = ProgressReport.from_table(data)

    assert len(report.children) == 2

    assert report.name is None
    assert report.current == 1 + 2 + 4 + 8
    assert report.total == 40

    assert report.children[0].name == 'one'
    assert report.children[0].current == 1 + 2
    assert report.children[0].total == 20
    assert len(report.children[0].children) == 2

    assert report.children[1].name == 'two'
    assert report.children[1].current == 4 + 8
    assert report.children[1].total == 20
    assert len(report.children[1].children) == 2
