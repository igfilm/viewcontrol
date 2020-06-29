import collections

from viewcontrol.util.timing import RenewableRepeatedTimer

callback_stack = list()


def _print_cycles(
    custom_arg,
    cycles_left,
    custom_kwarg1="default_kwarg1",
    custom_kwarg2="default_kwarg2",
    runtime_thread=-42,
):
    Args = collections.namedtuple(
        "Row",
        [
            "custom_arg",
            "cycles_left",
            "custom_kwarg1",
            "custom_kwarg2",
            "runtime_thread",
        ],
        rename=False,
    )
    args = Args(custom_arg, cycles_left, custom_kwarg1, custom_kwarg2, runtime_thread)
    content = f"printing: {args}"
    print(content)
    callback_stack.append(args)


def test_timer_argument_passing():
    global callback_stack
    callback_stack = list()
    timer = RenewableRepeatedTimer(
        0.5, _print_cycles, "custom_arg", cycles=3, custom_kwarg2="custom_kwarg2"
    )
    timer.start()
    timer.join()
    assert len(callback_stack) == 3
    args = callback_stack[-1]
    assert args.cycles_left >= 0
    assert args.custom_arg == "custom_arg"
    assert args.custom_kwarg1 == "default_kwarg1"
    assert args.custom_kwarg2 == "custom_kwarg2"
    assert args.runtime_thread >= 0
