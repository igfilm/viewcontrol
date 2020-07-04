import logging
import logging.config
import multiprocessing
import os
import pathlib
import queue
import threading

import mpv

from viewcontrol.util.timing import PausableRepeatedTimer


class ProcessMpv(multiprocessing.Process):
    """Dummy to starting MpvProcess as thread. See MpvProcess for args."""

    def __init__(
        self, logger_config, queue_send, queue_recv, fs_screen_num, stop_event
    ):
        super().__init__(name="ProcessMPV")
        self._dummy = MpvProcess(
            queue_send,
            queue_recv,
            self.name,
            fs_screen_num,
            stop_event,
            logger_config=logger_config,
        )

    def run(self):
        """Method to be run in sub-process; runs CommandProcess.run();"""
        self._dummy.run()


class ThreadMpv(threading.Thread):
    """Dummy to starting MpvProcess as thread. See MpvProcess for args."""

    def __init__(self, queue_send, queue_recv, fs_screen_num, stop_event):
        super().__init__(name="ThreadMpv")
        self._dummy = MpvProcess(
            queue_send,
            queue_recv,
            self.name,
            fs_screen_num,
            stop_event,
            logger_config=None,
        )

    def run(self):
        """Method representing the thread’s activity. Runs CommandProcess.run()"""
        self._dummy.run()


class MpvProcess:
    """Manages and starts threads of devices and handles communication.

    Args:
         queue_send (queue.Queue or multiprocessing.Queue): queue over which
            status messages of player will are send.
         queue_recv (queue.Queue or multiprocessing.Queue): queue over which
            commands are passed to the process/player.
         name_thread (str): name of thread ot process.
         fs_screen_num (int): In multi-monitor configurations, this option tells mpv
            which screen to display the video on.
         stop_event (threading.Event or multiprocessing.Event): Event object which
            will stop thread when set.
         logger_config (dict or None): pass a queue logger logger config (only when
            using multiprocessing). Default to None.

    """

    def __init__(
        self,
        queue_send,
        queue_recv,
        name_thread,
        fs_screen_num,
        stop_event,
        logger_config=None,
    ):
        self.stop_event = stop_event
        self.logger_config = logger_config
        self.queue_send = queue_send
        self.queue_recv = queue_recv
        self.name = name_thread
        self.fs_screen_num = fs_screen_num

        self._is_not_paused = threading.Event()
        self._is_not_paused.set()
        self.next_image_display_time_queue = queue.Queue()

        self.dummy_timer_running = False
        self.duration_next = None
        self.still_timer = None

        self.logger = None
        self.player = None

    def run(self):
        """Run function for thread/process, to be called by dummies."""

        # must be called in run
        if self.logger_config:
            logging.config.dictConfig(self.logger_config)
        self.logger = logging.getLogger()
        self.logger.info("Started '{}' with pid '{}'".format(self.name, os.getpid()))

        try:
            # initialize player
            self.player = mpv.MPV(log_handler=self._mpv_log, ytdl=False)
            self.player["title"] = "viewcontrol"
            self.player["fullscreen"] = True
            self.player["fs-screen"] = self.fs_screen_num
            self.player["on-all-workspaces"] = True
            self.player["keep-open"] = False
            self.player["osc"] = False
            self.player["image-display-duration"] = "INFINITY"

            self.player.observe_property("filename", self._mpv_observer_stat)
            self.player.observe_property("playlist-pos", self._mpv_observer_stat)
            self.player.observe_property("time-pos", self._mpv_observer_stat)
            self.player.observe_property("time-remaining", self._mpv_observer_stat)

            self._player_reset_playlist()
            self.dummy_timer_running = False
            start_image = True
            self.duration_next = None
            self.still_timer = None

            while not self.stop_event.is_set():
                # wait for data in queue, add file to playlist when data is
                # type str. Otherwise jump to next track (only used with still)
                try:
                    data = self.queue_recv.get(block=True, timeout=0.1)
                    self.logger.debug(
                        "--> received data: '{}':'{}'".format(type(data), str(data))
                    )

                    if isinstance(data, tuple):
                        filepath, duration = data
                        self.player.playlist_append(filepath)
                        self.duration_next = duration
                        self.logger.info(
                            "Appending File {} at pos {} in playlist.".format(
                                str(data), len(self.player.playlist)
                            )
                        )
                        if start_image:
                            self._player_next()
                            start_image = False
                    elif isinstance(data, str):
                        if data == "pause":
                            if self._playing:
                                self._player_pause()
                        elif data == "resume":
                            if not self._playing:
                                self._player_resume()
                        elif data == "next":
                            self._player_next()

                except queue.Empty:
                    continue

            self.player.terminate()

            self.logger.info("stop flag set. terminated processmpv")

        except Exception as e:
            try:
                raise
            finally:
                self.logger.error(
                    "Uncaught exception in process '{}'".format(self.name), exc_info=e
                )

    @property
    def _playing(self):
        if self._is_not_paused.is_set():
            return True
        else:
            return False

    @property
    def is_paused(self):
        if not self._is_not_paused.is_set():
            return True
        return False

    def _player_pause(self):
        self.player["pause"] = True
        if self.still_timer:
            self.still_timer.pause()
        self._is_not_paused.clear()

    def _player_resume(self):
        self.player["pause"] = False
        if self.still_timer:
            self.still_timer.resume()
        self._is_not_paused.set()

    def _player_next(self):
        if self.still_timer:
            self.still_timer.cancel()
            self.still_timer = None
        self.player.playlist_next()

    def _mpv_log(self, log_level, _, message):
        """passes mpv log massages to python logger."""
        if log_level == "fatal":
            level = 50
        elif log_level == "error":
            level = 40
        elif log_level == "warn":
            level = 30
        elif log_level == "info":
            level = 20
        elif logging in ["v", "debug", "trace"]:
            level = 10
        else:
            level = 0
        self.logger.log(level, "MPV:" + message)

    def _mpv_observer_stat(self, prop, value):
        """relays status messages of interest to main thread (viewcontrol)"""
        tuple_send = (prop, value)
        if prop == "time-pos" or prop == "time-remaining":
            if value:
                value = round(value, 4)
            tuple_send = (prop, value)
        elif prop == "playlist-pos":
            if value == 0:
                self.logger.debug(
                    "<-- Omitting {}. Property change not send.".format(tuple_send)
                )
                return
            elif value is None:
                self._player_reset_playlist()
            else:
                if self.duration_next:
                    self.still_timer = PausableRepeatedTimer(
                        0.1,
                        self._timer_handler_repeat,
                        cycles=int(self.duration_next / 0.1),
                        handler_end=self._timer_handler_end,
                    )
                    self.still_timer.start()
                    if not self._is_not_paused.is_set():
                        self.still_timer.pause()

        self.queue_send.put(tuple_send)
        logging.getLogger().log(
            0, "<-- send data: '{}':'{}'".format(type(tuple_send), str(tuple_send))
        )

    def _timer_handler_repeat(self, runtime_cycle, time_left_cycle):
        self._mpv_observer_stat("time-pos", runtime_cycle)
        self._mpv_observer_stat("time-remaining", time_left_cycle)

    def _timer_handler_end(self, runtime_cycle, time_left_cycle):
        self._timer_handler_repeat(runtime_cycle, time_left_cycle)
        self._player_next()

    def _player_reset_playlist(self):
        self.player.play(str(viewcontrol_picture_path()))
        self.player["image-display-duration"] = "INFINITY"


# TODO move function in the util package when it is created (duplicate in show)
def data_folder_path() -> pathlib.Path:
    return pathlib.Path(__file__).parent.parent.joinpath("data")


def viewcontrol_picture_path() -> pathlib.Path:
    return data_folder_path().joinpath("viewcontrol.png")
