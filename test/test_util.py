import collections
import time

from viewcontrol.util.timing import PausableRepeatedTimer
from viewcontrol.util.timing import RepeatedTimer
from viewcontrol.util.timing import PausableTimer

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
    timer = PausableRepeatedTimer(
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


def test_timer_time_rest():
    timer = RepeatedTimer(0.2, RepeatedTimer.do_nothing, duration=3.14)
    t_start = time.perf_counter()
    timer.start()
    timer.join()
    t_stop = time.perf_counter()
    runtime = t_stop - t_start
    print(runtime)
    assert runtime < 3.141
    assert runtime > 3.139


def test_timer_pause():
    timer = PausableRepeatedTimer(0.2, RepeatedTimer.do_nothing, cycles=10)
    t_start = time.perf_counter()
    timer.start()
    time.sleep(1)
    timer.pause()
    t_pause = time.perf_counter()
    while time.perf_counter() - t_pause < 1:
        pass
    timer.resume()
    timer.join()
    t_stop = time.perf_counter()
    runtime = t_stop - t_start
    print(runtime)
    assert runtime < 3.001
    assert runtime > 2.999


def test_timer_renewable_only():
    timer = PausableTimer(1.998, RepeatedTimer.do_nothing)
    t_start = time.perf_counter()
    timer.start()
    time.sleep(1)
    timer.pause()
    t_pause = time.perf_counter()
    while time.perf_counter() - t_pause < 1:
        pass
    timer.resume()
    timer.join()
    t_stop = time.perf_counter()
    runtime = t_stop - t_start
    print(runtime)
    assert runtime < 3.000
    assert runtime > 2.996
