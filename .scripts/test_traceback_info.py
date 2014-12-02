import traceback


def function_one(arg):
    return function_two(arg + ['one'])


def function_two(arg):
    foo = 'Some string'
    foo += '!'
    return function_three(arg + ['two'])


def function_three(arg):
    bar = 'THIS IS SOME'
    bar += ' TEXT'
    raise ValueError(str(arg + ['three']))


from jobcontrol.utils import TracebackInfo


try:
    function_one([])
except:
    tbi = TracebackInfo.from_current_exc()

    print(traceback.format_exc())
    print('\n\n\n\n')
    print(tbi)
    print('\n\n\n\n')
    print(tbi.format_color())
