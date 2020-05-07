import multiprocessing
import threading
import functools
import os
import logging
import logging.config
import time
import queue

import mpv


class ProcessMpv(multiprocessing.Process):
    def __init__(self, logger_config, queue_send, queue_recv, fs_screen_num):
        super().__init__(name="ProcessMPV")
        self._dummy = DummyMpv(
            logger_config, queue_send, queue_recv, self.name, fs_screen_num
        )

    def run(self):
        self._dummy.run()


class ThreadMpv(threading.Thread):
    def __init__(self, logger, queue_send, queue_recv, fs_screen_num):
        super().__init__(name="ThreadMpv")
        self._dummy = DummyMpv(logger, queue_send, queue_recv, self.name, fs_screen_num)

    def run(self):
        self._dummy.run()


class DummyMpv:
    def __init__(
        self, logger_config, queue_send, queue_recv, parent_name, fs_screen_num
    ):
        self.logger_config = logger_config
        self.queue_send = queue_send
        self.queue_recv = queue_recv
        self.name = parent_name
        self.fs_screen_num = fs_screen_num

        self.can_run = threading.Event()
        self.can_run.set()

    def run(self):
        if isinstance(self.logger_config, logging.Logger):
            self.logger = self.logger_config
        else:
            logging.config.dictConfig(self.logger_config)
            self.logger = logging.getLogger()
        self.logger.info("Started '{}' with pid '{}'".format(self.name, os.getpid()))

        try:
            # initilaize player
            self.player = mpv.MPV(log_handler=self.mpv_log, ytdl=False)
            self.player["fullscreen"] = True
            self.player["fs-screen"] = self.fs_screen_num
            self.player["on-all-workspaces"] = True
            self.player["keep-open"] = False
            self.player["osc"] = False

            self.player.observe_property("filename", self.mpv_observer_stat)
            self.player.observe_property("playlist-pos", self.mpv_observer_stat)
            self.player.observe_property("time-pos", self.mpv_observer_stat)
            self.player.observe_property("time-remaining", self.mpv_observer_stat)

            self.player_reset_playlist()
            self.dummy_timer_running = False
            start_image = True

            self.next_image_display_time_queue = queue.Queue()

            while True:
                # wait for data in queue, add file to playlist when data is
                # type str. Otherwse jump to next track (only used with still)
                data = self.queue_recv.get()
                self.logger.debug(
                    "--> recived data: '{}':'{}'".format(type(data), str(data))
                )

                if isinstance(data, tuple):
                    filepath, duration = data
                    self.next_image_display_time_queue.put(duration)
                    self.player.playlist_append(filepath)
                    self.logger.info(
                        "Appending File {} at pos {} in playlist.".format(
                            str(data), len(self.player.playlist)
                        )
                    )
                    if start_image:
                        self.playlist_next()
                        start_image = False
                elif isinstance(data, str):
                    if data == "pause":
                        if self.playing:
                            self.player_pause()
                    elif data == "resume":
                        if not self.playing:
                            self.player_resume()
                    elif data == "next":
                        pass
                        # self.playlist_next()

        except Exception as e:
            try:
                raise
            finally:
                self.logger.error(
                    "Uncaught exception in process '{}'".format(self.name), exc_info=(e)
                )

    @property
    def playing(self):
        if self.can_run.is_set():
            return True
        else:
            return False

    def player_pause(self):
        self.player["pause"] = True
        self.can_run.clear()

    def player_resume(self):
        self.player["pause"] = False
        self.can_run.set()

    def playlist_next(self):
        self.player.playlist_next()

    def mpv_log(self, loglevel, component, message):
        if loglevel == "fatal":
            level = 50
        elif loglevel == "error":
            level = 40
        elif loglevel == "warn":
            level = 30
        elif loglevel == "info":
            level = 20
        elif logging in ["v", "debug", "trace"]:
            level = 10
        else:
            level = 0
        self.logger.log(level, "MPV:" + message)

    def mpv_observer_stat(self, prop, value):
        obj_send = (prop, value)
        if prop == "time-pos" or prop == "time-remaining":
            if not self.dummy_timer_running:
                if value:
                    value = round(value, 4)
                self.queue_send.put((prop, value))
            return
        elif prop == "d_time-pos" or prop == "d_time-remaining":
            if self.dummy_timer_running:
                self.queue_send.put((prop[2:], round(value, 4)))
            return
        elif prop == "playlist-pos":
            if value == 0:
                self.logger.debug(
                    "<-- Ommiting {}. Property change not send.".format(obj_send)
                )
                return
            elif value == None:
                self.player_reset_playlist()
            else:
                t = self.next_image_display_time_queue.get()
                if t:
                    self.dummy_timer_running = True
                    self.player["image-display-duration"] = t
                    threading.Thread(target=self.thread_time_dummy, args=(t,)).start()
                else:
                    self.dummy_timer_running = False
                    self.player["image-display-duration"] = "INFINITY"

        self.queue_send.put(obj_send)
        self.logger.debug(
            "<-- send data: '{}':'{}'".format(type(obj_send), str(obj_send))
        )

    def thread_time_dummy(self, duration, fps=10):
        tr = duration
        dt = 1 / fps
        self.mpv_observer_stat("d_time-pos", 0)
        self.mpv_observer_stat("d_time-remaining", duration)
        while tr > 0.001:  #  WARNING time offset through process times
            self.can_run.wait()
            time.sleep(dt - 0.00029)
            tr -= dt
            self.mpv_observer_stat("d_time-pos", duration - tr)
            self.mpv_observer_stat("d_time-remaining", tr)

    def player_reset_playlist(self):
        self.player.play("media/viewcontrol.png")
        self.player["image-display-duration"] = "INFINITY"
