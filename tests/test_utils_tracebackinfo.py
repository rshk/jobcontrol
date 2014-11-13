from jobcontrol.utils import TracebackInfo, FrameInfo


def test_traceback_info():
    offset = 4  # Previous line number

    def myfunction():
        foobar = "Foo Bar"
        return myfunction2(foobar)

    def myfunction2(foo):
        name = "world"
        name = name.upper()  # do something w/ it
        raise ValueError("This is an exception")

    try:
        myfunction()  # Error line: 13 from start
    except ValueError:
        tbinfo = TracebackInfo.from_current_exc()
    else:
        raise AssertionError("Did not raise -- WTF?")

    assert len(tbinfo.frames) == 3

    assert tbinfo.frames[0].filename == __file__
    assert tbinfo.frames[0].lineno == offset + 13
    assert tbinfo.frames[0].name == 'test_traceback_info'
    assert tbinfo.frames[0].line == \
        'myfunction()  # Error line: 13 from start'
    assert tbinfo.frames[0].context == [
        (offset + 8, '        name = "world"'),
        (offset + 9, '        name = name.upper()  # do something w/ it'),
        (offset + 10, '        raise ValueError("This is an exception")'),
        (offset + 11, ''),
        (offset + 12, '    try:'),
        (offset + 13, '        myfunction()  # Error line: 13 from start'),
        (offset + 14, '    except ValueError:'),
        (offset + 15, '        tbinfo = TracebackInfo.from_current_exc()'),
        (offset + 16, '    else:'),
        (offset + 17, '        raise AssertionError("Did not raise -- WTF?")'),
        (offset + 18, ''),
    ]

    assert tbinfo.frames[1].filename == __file__
    assert tbinfo.frames[1].lineno == offset + 5
    assert tbinfo.frames[1].name == 'myfunction'
    assert tbinfo.frames[1].line == \
        'return myfunction2(foobar)'

    assert tbinfo.frames[2].filename == __file__
    assert tbinfo.frames[2].lineno == offset + 10
    assert tbinfo.frames[2].name == 'myfunction2'
    assert tbinfo.frames[2].line == \
        'raise ValueError("This is an exception")'


def test_context_extraction():
    ctx = FrameInfo(__file__, 2, '', '', {})._get_context(2)
    assert len(ctx) == 4
    assert ctx[0] == (1, 'from jobcontrol.utils import TracebackInfo, FrameInfo')  # noqa

    ctx = FrameInfo(__file__, 66, '', '', {})._get_context(2)
    assert len(ctx) == 3  # Last blank line is not counted
    assert ctx[2] == (66, '    # End line')

    # End line
