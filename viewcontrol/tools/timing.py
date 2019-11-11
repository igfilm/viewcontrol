from threading import Timer
import time

class RenewableTimer():

    def __init__(self, interval, function, *args, **kwargs):
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.timer = Timer(self.interval, self.function, self.args, self.kwargs)
        self.timer.name = "fuubar"
        self.timer_runnig = False

    def cancel(self):
        self.timer.cancel()

    def start(self):
        self.start_time = time.time()
        self.timer_runnig = True
        self.timer.start()
        
    def pause(self):
        self.cancel_time = time.time()
        self.timer_runnig = False
        self.timer.cancel()
        return self.actual_time

    def resume(self):
        self.interval = self.actual_time
        self.timer = Timer(self.interval, self.function, self.args, self.kwargs)
        self.start()

    @property
    def actual_time (self):
        if not self.timer or not self.timer.isAlive:
            return None
        elif self.timer_runnig:
            return self.interval - (time.time() - self.start_time)
        else:
            return self.interval - (self.cancel_time - self.start_time)
