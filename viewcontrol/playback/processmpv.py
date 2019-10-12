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
    
    def __init__(self, logger_config, queue_send, queue_recv):
        super().__init__(name='BenjaminBluemchen')
        self._dummy = DummyMpv(logger_config, queue_send, queue_recv, self.name)

    def run(self):
        self._dummy.run()

class ThreadMpv(threading.Thread):

    def __init__(self, logger, queue_send, queue_recv):
        super().__init__(name='BenjaminBluemchen')
        self._dummy = DummyMpv(logger, queue_send, queue_recv, self.name)

    def run(self):
        self._dummy.run()

class DummyMpv:
    
    def __init__(self, logger_config, queue_send, queue_recv, parent_name):
        self.logger_config = logger_config
        self.queue_send = queue_send
        self.queue_recv = queue_recv
        self.name = parent_name

    def run(self):
        if isinstance(self.logger_config, logging.Logger):
            self.logger = self.logger_config
        else:
            logging.config.dictConfig(self.logger_config)
            self.logger = logging.getLogger()
        self.logger.info("Started '{}' with pid '{}'".format(self.name, os.getpid()))

        try:
            #initilaize player
            self.player = mpv.MPV(log_handler=self.mpv_log, ytdl=False)
            self.player['fullscreen'] = True
            self.player['fs-screen'] = 10
            self.player['on-all-workspaces'] = True
            self.player['keep-open'] = False
            self.player['osc'] = False

            self.player.observe_property('filename', self.mpv_observer_stat)
            self.player.observe_property('playlist-pos', self.mpv_observer_stat)
            self.player.observe_property('time-pos', self.mpv_observer_stat)
            self.player.observe_property('time-remaining', self.mpv_observer_stat)

            self.player_reset_playlist()
            start_image = True

            self.next_image_display_time_queue = queue.Queue()

            while True:
                # wait for data in queue, add file to playlist when data is
                # type str. Otherwse jump to next track (only used with still)
                data = self.queue_recv.get()
                self.logger.debug("--> recived data: '{}':'{}'"
                    .format(type(data), str(data)))

                filepath, time = data
                self.next_image_display_time_queue.put(time)  
                self.player.playlist_append(filepath)
                self.logger.info("Appending File {} at pos {} in playlist.".format(str(data), len(self.player.playlist)))
                if start_image:
                    self.playlist_next()
                    start_image = False

        except Exception as e:
            try:
                raise
            finally:
                self.logger.error("Uncaught exception in process '{}'"
                        .format(self.name), 
                    exc_info=(e))

    def playlist_next(self):
        self.player.playlist_next()
        

    def mpv_log(self, loglevel, component, message):
        if loglevel == "fatal":
            level = 50
        elif loglevel == "error":
            level = 40
        elif loglevel == "warn":
            level = 30
        elif loglevel =="info":
            level = 20
        elif logging in ["v", "debug", "trace"]:
            level = 10
        else:
            level = 0
        self.logger.log(level, "MPV:" + message)


    def mpv_observer_stat(self, prop, value):
        obj_send = (prop, value)
        if prop == 'time-pos' or prop == 'time-remaining':
            self.queue_send.put(obj_send)
            return
        elif prop == "playlist-pos":
            if value==0:
                self.logger.debug("<-- Ommiting {}. Property change not send."
                    .format(obj_send))
                return
            elif value==None:
                self.player_reset_playlist()
            else:
                t = self.next_image_display_time_queue.get()
                if t:
                    self.player['image-display-duration'] = t
                    threading.Thread(target=self.thread_time_dummy, args=(t,)).start()
                else:
                    self.player['image-display-duration'] = 'INFINITY'
            
        self.queue_send.put(obj_send)
        self.logger.debug("<-- send data: '{}':'{}'"
            .format(type(obj_send), str(obj_send)))

    def thread_time_dummy(self, duration, fps=10):
        tr = duration
        dt = 1/fps
        self.mpv_observer_stat('time-pos', 0)
        self.mpv_observer_stat('time-remaining', duration)
        while tr>0.001:  #  WARNING time offset through process times
            time.sleep(dt)
            tr -= dt
            self.mpv_observer_stat('time-pos', duration-tr)
            self.mpv_observer_stat('time-remaining', tr)

    def player_reset_playlist(self):
        self.player.play('media/viewcontrol.png')
        self.player['image-display-duration'] = 'INFINITY'

"""
    def def_process_mpv(self, logger_config, pipe_mpv_statl, queue_mpv):
        pname=multiprocessing.current_process().name
        logging.config.dictConfig(logger_config)
        logger = logging.getLogger(pname)
        logger.info("Started process_mpv with pid {}".format(os.getpid()))
        
        try:
            # mpv expects logger func without a logger, therfore create new funtion
            # with log already filled in  
            mpv_log = functools.partial(self.mpv_log, log=logger)

            #initilaize player
            player = mpv.MPV(log_handler=mpv_log, ytdl=False)
            player.fullscreen = True
            player['fs-screen'] = self.screen_id
            player['image-display-duration'] = 5
            player['keep-open'] = True
            player['osc'] = False

            handler_mpv_observer_stat = functools.partial(self.mpv_observer_stat, log=logger, pipe=pipe_mpv_statl)
            player.observe_property('filename', handler_mpv_observer_stat)
            player.observe_property('playlist-pos', handler_mpv_observer_stat)
            #first immage to avoid idle player
            player.playlist_append('media/viewcontrol.png')

            while True:

                # wait for data in queue, add file to playlist when data is
                # type str. Otherwse jump to next track (only used with still)
                if not queue_mpv.empty():
                    data = queue_mpv.get()
                    if isinstance(data, str):                
                        player.playlist_append(data)
                        logger.error("Appending File {} at pos {} in playlist.".format(str(data), len(player.playlist)))
                    else:
                        player.playlist_next()
                        logger.error("Call playlist_next")
                else:
                    time.sleep(.005)
                
        except Exception as e:
            try:
                raise
            finally:
                logger.error("Uncaught exception in process '{}'"
                        .format(pname), 
                    exc_info=(e))
"""