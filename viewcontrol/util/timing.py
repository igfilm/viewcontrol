import inspect
import threading
import time


class RepeatedTimer:
    """Timer which restarts itself after it has run out and calls a function.

    Class attributes can be passed to handler function by writing theme as arg or kwarg
    inf function arguments. Function arguments will always be overwritten.

    The timer has less 1 ms a precision . Using
    a the wait function of threading.Event

    The timer has a precision of less than one milliseconds (depending on load an cpu
    of course). The timer itself is an object in which a thread (daemon) is running
    (which also calls the handler functions!).

    Args:
        interval(float): time between repetitions/cycles
        handler_repeat (function): function called after each cycle. If function end is
            not None, it is called at the end instead of function_repeat
        cycles(int, optional): runs the timer n times and calls function_repeat
            after each cycle. If cycles is negative it will run indefinitely.
            If cycles and duration are none, cycles is set to -1 (infinity).
            Defaults to None.
        duration(float, optional): if cycles is None, calculates the cycles needed to
            run out in given time with given interval. If duration is not a multiple of
            interval, the "rest-time-interval" will be tun lastIgnored if cycles is not
            None. Defaults to None.
        handler_end (function or None, optional): function called at the end
            instead of function_repeat. If None, function_repeat is called.
            Default to None.

    Attributes:
        interval (float): time between each cycle.
        cycles (int): number of cycles to run.
        cycles_left (int): number of cycles left.
        handler_repeat (function): function handler to be called after each cycle
        handler_end (function or None): unction handler to be called at the end (also
            see Argument description with same name).

    """

    self_attr = {
        "is_running",
        "total_running_time",
        "runtime_thread",
        "time_left_thread",
        "runtime_cycle",
        "time_left_cycle",
        "interval",
        "cycles",
        "cycles_left",
        "duration",
        "rest",
    }

    def __init__(
        self,
        interval,
        handler_repeat,
        *args,
        cycles=None,
        duration=None,
        handler_end=None,
        **kwargs,
    ):
        self.interval = interval
        self.handler_repeat = handler_repeat
        self.handler_end = handler_end
        self.rest = 0
        if not cycles and not duration:
            cycles = -1
        elif duration:
            cycles, self.rest = divmod(duration, interval)
        if self.rest > 0:
            cycles += 1
        self.cycles = cycles
        self.cycles_left = cycles
        self._start_time = None
        self._time_offset = 0
        self._ticker = threading.Event()
        self._is_running = threading.Event()
        self._is_finished = threading.Event()
        self._is_finished.clear()
        self._is_not_paused = threading.Event()
        self._is_not_paused.set()
        self._thread = None
        self._args = args
        self._kwargs = kwargs

    def _run(self):

        while not self._ticker.is_set():
            interval = self.interval
            if self.cycles_left == 1 and self.rest > 0:
                interval = self.rest
            # compensate offset of last run and/or pause
            i = interval - (self.runtime_thread - self.runtime_cycle)
            if i < 0:
                i = 0
            self._ticker.wait(i)
            if not self._is_not_paused.is_set():
                self._is_not_paused.wait()
                continue
            if not self._is_running.is_set():
                break
            self.cycles_left -= 1
            if self.cycles_left == 0:
                if self.handler_end:
                    self._compose_and_call(self.handler_end)
                else:
                    self._compose_and_call(self.handler_repeat)
                self._is_finished.set()
                self._is_running.clear()
                break
            self._compose_and_call(self.handler_repeat)

    def start(self):
        """start the timer

         Returns:
             bool: true if successful

        """
        if not self._is_running.is_set():
            self._ticker.clear()
            self._is_running.set()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._start_time = time.perf_counter()
            self._thread.start()
            return True
        return False

    def cancel(self):
        """stop the timer

         Returns:
             bool: true if successful

        """
        if self._is_running.is_set():
            self._is_running.clear()
            self._ticker.set()
            return True
        return False

    def _compose_and_call(self, func):
        cur_arg = 0
        args = list()
        kwargs = dict()
        for param in inspect.signature(func).parameters.values():
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                pass
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                pass
            elif param.kind == inspect.Parameter.KEYWORD_ONLY or (
                param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
                and param.default is not param.empty
            ):
                if param.name in self.self_attr:
                    kwargs[param.name] = getattr(self, param.name)
                elif param.name in self._kwargs.keys():
                    kwargs[param.name] = self._kwargs[param.name]
                else:
                    pass  # do nothing use default value
            else:
                if param.name in self.self_attr:
                    args.append(getattr(self, param.name))
                elif param.name in self._kwargs.keys():
                    args.append(self._kwargs.get(param.name))
                elif cur_arg < len(self._args):
                    args.append(self._args[cur_arg])
                    cur_arg += 1
                else:
                    raise ValueError(f"positional argument '{param.name}' missing")

        func(*args, **kwargs)

    def join(self):
        """block until timer has run out"""
        if not self.is_running:
            raise RuntimeError("timer not running")
        return self._is_finished.wait()

    @property
    def is_running(self):
        """Return true if timer is running."""
        return self._is_running.is_set()

    @property
    def total_running_time(self):
        """total time the timer is supposed to run

        Returns:
            float or None: time or None if timer runs in endless loop

        """
        if self.cycles < 0:
            return (self.cycles + 1) * self.interval
        return self.interval * self.cycles

    @property
    def runtime_thread(self):
        """total time the timer has run (invalid van timer was paused)

        Returns:
            float: time the timer has run

        """
        return time.perf_counter() - self._start_time + self._time_offset

    @property
    def time_left_thread(self):
        """time left calculated from system time (invalid van timer was paused)

        Returns:
            float or None: time or None if timer runs in endless loop

        """
        if self.cycles < 0:
            return None
        return self.total_running_time - self.runtime_thread

    @property
    def runtime_cycle(self):
        """time already completed calculated from cycles

        Returns:
            float: time the timer has run

        """
        return abs((self.cycles - self.cycles_left) * self.interval)

    @property
    def time_left_cycle(self):
        """time left calculated from cycles

        Returns:
            float or None: time or None if timer runs in endless loop

        """
        if self.cycles < 0:
            return None
        return self.cycles_left * self.interval

    @staticmethod
    def do_nothing():
        """use at end_handler if you don't wan't anything to happen after last cycle."""
        pass


class PausableRepeatedTimer(RepeatedTimer):
    """Same as RepeatedTimer but can be paused. See RepeatedTimer.

    PausableTimer is being a extra class by purpose (although parts of it are
    implemented in RepeatedTimer) to give the programmer the explicit choice to use
    a (not) pausable timer.
    """

    self_attr = RepeatedTimer.self_attr.union("is_paused")

    def __init__(
        self,
        interval,
        handler_repeat,
        *args,
        cycles=None,
        duration=None,
        handler_end=None,
        **kwargs,
    ):
        super().__init__(
            interval,
            handler_repeat,
            *args,
            cycles=cycles,
            duration=duration,
            handler_end=handler_end,
            **kwargs,
        )
        self._pause_time = None

    def pause(self):
        """pause the timer

         Returns:
             bool: true if successful

        """
        if self.is_running and not self.is_paused:
            self._pause_time = time.perf_counter()
            self._is_not_paused.clear()
            self._ticker.set()
            return True
        return False

    def resume(self):
        """resume the timer

         Returns:
             bool: true if successful

        """
        if self.is_running and self.is_paused:
            self._time_offset += self._pause_time - time.perf_counter()
            self._ticker.clear()
            self._is_not_paused.set()
            return True
        return False

    @property
    def is_paused(self):
        """Return true if timer is running but paused."""
        if self.is_running:
            return not self._is_not_paused.is_set()
        return False


class PausableTimer(PausableRepeatedTimer):
    """Renewable timer that only runs once.

    PausableTimer is basically PausableRepeatedTimer with an simplified class
    initializer. Got the same function signature as threading.Timer.

    Args:
        interval(float, optional): time after which function is run.
        function (function): function called when timer has run out.

    """

    def __init__(self, interval, function, *args, **kwargs):
        super().__init__(
            interval,
            PausableTimer.do_nothing,
            *args,
            cycles=1,
            # duration=duration,
            handler_end=function,
            **kwargs,
        )


def timer_handler_repeat_test(
    total_running_time,
    runtime_thread,
    runtime_cycle,
    time_left_thread,
    time_left_cycle,
):
    """For Testing Only

    simple handler function to print time times (exact and calculated).

    """
    print(
        "{:+f} {}   {:+f}   {:+f} - {:+f} = {:+f}   {:+f} - {:+f} = {:+f}".format(
            time.perf_counter(),
            threading.currentThread().name,
            total_running_time,
            runtime_thread,
            runtime_cycle,
            runtime_thread - runtime_cycle,
            time_left_thread,
            time_left_cycle,
            time_left_thread - time_left_cycle,
        )
    )
