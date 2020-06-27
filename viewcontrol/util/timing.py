from threading import Timer
import time


class RepeatedTimer:
    """Timer which restarts itself after int run out."""

    def __init__(self, interval, function, *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.is_running = False

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def cancel(self):
        if self._timer:
            self._timer.cancel()
            self.is_running = False


class RenewableTimer:
    """Timer which can be paused and resumed."""

    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self._timer = Timer(self.interval, self.function, self.args, self.kwargs)
        self._timer.name = "RenewableTimer"
        self._timer_running = False
        self.start_time = None
        self.cancel_time = None

    def cancel(self):
        self._timer.cancel()

    def start(self):
        self.start_time = time.time()
        self._timer_running = True
        self._timer.start()

    def pause(self):
        self.cancel_time = time.time()
        self._timer_running = False
        self._timer.cancel()
        return self.actual_time

    def resume(self):
        self.interval = self.actual_time
        self._timer = Timer(self.interval, self.function, self.args, self.kwargs)
        self.start()

    @property
    def actual_time(self):
        if not self._timer or not self._timer.is_alive():
            return None
        elif self._timer_running:
            return self.interval - (time.time() - self.start_time)
        else:
            return self.interval - (self.cancel_time - self.start_time)

    @property
    def running(self):
        return self._timer_running
