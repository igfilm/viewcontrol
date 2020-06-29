import inspect
import threading
import time


class RepeatedTimer:
    """Timer which restarts itself after it has run out and calls a function.

    Class attributes can be passed to handler function by writing theme as arg or kwarg
    inf function arguments. Function arguments will always be overwritten.

    time is measured with number of cycles and interval length. Actual runtime will be
    always a bit longer than real time (<1%) due to processing delays.

    TODO fix this so timer will be exact by using a time corrected interval in wait
    TODO add option to use time  directly and not intervals to allow for large intervals

    Args:
        interval(float): time between repetitions/cycles
        handler_repeat (function): function called after each cycle. If function end is
            not None, it is called at the end instead of function_repeat
        cycles(int, optional): runs the timer n times and calls function_repeat
            after each cycle. If cycles is negative it will run indefinitely.
            If cycles and duration are none, cycles is set to -1 (infinity).
            Defaults to None.
        duration(float, optional): if cycles is None, calculates the cycles needed to
            run out in given time with given interval. Ignored if cycles is not None.
            Defaults to None.
        handler_end (function or None, optional): function called at the end
            instead of function_repeat. If None function_repeat is called.
            Default to None.

    """

    self_attr = {
        "running",
        "interval",
        "cycles",
        "cycles_left",
        "total_running_time",
        "runtime_thread",
        "runtime_cycle",
        "time_left_thread",
        "time_left_cycle",
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
        if not cycles and not duration:
            cycles = -1
        elif duration:
            cycles = int(duration / interval)
        self.cycles = cycles
        self.cycles_left = cycles
        self._start_time = None
        self._ticker = threading.Event()
        self._is_running = threading.Event()
        self._is_finished = threading.Event()
        self._is_finished.clear()
        self._thread = None
        self._args = args
        self._kwargs = kwargs

    def _run(self):
        while not self._ticker.wait(self.interval):
            self.cycles_left -= 1
            if not self._is_running.is_set():
                break
            if self.cycles_left == 0:
                if self.handler_end:
                    self._compose_and_call(self.handler_end)
                    # self.handler_end(**self._compose_kwargs_from_att(self.handler_end))
                else:
                    self._compose_and_call(self.handler_repeat)
                    # self.handler_repeat(
                    #     **self._compose_kwargs_from_att(self.handler_repeat)
                    # )
                self._is_finished.set()
                break
            self._compose_and_call(self.handler_repeat)
            # self.handler_repeat(**self._compose_kwargs_from_att(self.handler_repeat))

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

        # func_args = set(inspect.signature(func).parameters)
        # kwargs = self._kwargs.copy()
        # for arg in func_args & self.self_attr:
        #     kwargs[arg] = getattr(self, arg)

        func(*args, **kwargs)

    def join(self):
        """block until timer has run out"""
        return self._is_finished.wait()

    @property
    def is_running(self):
        """Return true if timer is running"""
        return self._is_running.is_set()

    @property
    def total_running_time(self):
        """total time the timer is supposed to run

        Returns:
            float or None: time or None if timer runs in endless loop

        """
        if self.cycles < 0:
            return None
        return self.interval * self.cycles

    @property
    def runtime_thread(self):
        """total time the timer has run (invalid van timer was paused)

        Returns:
            float: time the timer has run

        """
        return time.perf_counter() - self._start_time

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


class RenewableRepeatedTimer(RepeatedTimer):
    """Same as RepeatedTimer but can be paused. See RepeatedTimer."""

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
        self._is_paused = threading.Event()
        self._is_paused.clear()
        self.rest_time = None
        self._cancel_time = None

    def start(self):
        """stop the timer

         Returns:
             bool: true if successful

        """
        self._is_paused.clear()
        return super().start()

    def pause(self):
        """pause the timer

         Returns:
             bool: true if successful

        """
        self._cancel_time = time.time()
        self.cancel()
        self.rest_time = self.runtime_thread
        return self.rest_time

    def resume(self):
        """resume the timer

             Returns:
                 bool: true if successful

            """
        if self.start():
            self.rest_time = None
            return True
        return False

    @property
    def is_paused(self):
        return self._is_paused.is_set()

    @property
    def actual_time(self):

        if self._is_paused:
            return self._cancel_time - self._start_time
        else:
            return None


class RenewableTimer(RenewableRepeatedTimer):
    """Renewable timer that only runs once with 100ms accuracy.

    Will be improved when RenewableRepeatedTimer is updated to optional work with time
    and not with steps and intervals.

    Args:
        duration(float, optional): if cycles is None, calculates the cycles needed to
            run out in given time with given interval. Ignored if cycles is not None.
            Defaults to None.
        handler_end (function None, optional): function called at the end
            instead of function_repeat. If None function_repeat is called.
            Default to None.

    """

    def __init__(self, duration, handler_end, *args, **kwargs):
        super().__init__(
            0.01,
            RenewableTimer.do_nothing,
            *args,
            duration=duration,
            handler_end=handler_end,
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
        "{}:{:+f}, {:+f}:{:+f}, {:+f}:{:+f}".format(
            threading.currentThread().name,
            total_running_time,
            runtime_thread,
            runtime_cycle,
            time_left_thread,
            time_left_cycle,
        )
    )
