import multiprocessing
import threading
import queue
import time
import logging
import logging.config
import logging.handlers
import os
import sys
import optparse
import yaml

import sqlalchemy
from sqlalchemy import create_engine

from blinker import signal

import functools


import viewcontrol.vctools as vctools

import mpv

import viewcontrol.show as show
from viewcontrol.remotec.commandprocess import CommandProcess
from viewcontrol.playback.processmpv import ProcessMpv, ThreadMpv

class ViewControl(object):

    multiprocess = False

    def __init__(self, args):

        #Loading Logger with Configutation File
        logger_config_path = 'logging.yaml'
        if os.path.exists(logger_config_path):
            with open(logger_config_path, 'rt') as f:
                config_log = yaml.safe_load(f.read())
            logging.config.dictConfig(config_log)
        else:
            logging.basicConfig(level=logging.INFO)

        self.logger = logging.getLogger(threading.current_thread().name)
        self.logger.info("###################################")

        #Add logging with traceback for all unhandled exeptions in main thread
        sys.excepthook = self.handle_exception

        # Queue to enable logging from proscesses to one single file
        if ViewControl.multiprocess:
            q = multiprocessing.Queue()
        else:
            q = queue.Queue()
        self.config_queue_logger = {
            'version': 1,
            'disable_existing_loggers': True,
            'handlers': {
                'queue': {
                    'class': 'logging.handlers.QueueHandler',
                    'queue': q,
                },
            },
            'root': {
                'level': 'DEBUG',
                'handlers': ['queue']
            },
        }

        # Create and Start thread_logger
        self.lp = threading.Thread(
            target=self.thread_logger, 
            args=(q,), 
            name='thread_logger',
            daemon=True)
        self.lp.start()
        self.logger.info("Started '{}' with pid 'N.A.'".format(self.lp.name, ))

        if ViewControl.multiprocess:
            self.command_queue = multiprocessing.Queue()
            self.status_queue = multiprocessing.Queue()
            self.mpv_controll_queue = multiprocessing.Queue()
            self.mpv_status_queue = multiprocessing.Queue()
        else:
            self.command_queue = queue.Queue()
            self.status_queue = queue.Queue()
            self.mpv_controll_queue = queue.Queue()
            self.mpv_status_queue = queue.Queue()

        # setup event mpv
        self.sig_mpv_prop = signal("mpv_prop_chaged")
        self.lm = threading.Thread(
            target=self.thread_listen_process_mpv,
            name='listen_process_mpv',
            daemon=True
        )
        self.lm.start()
        self.sig_mpv_prop.connect(self.subscr_listen_process_mpv)

        # setup event cmd
        self.sig_cmd_prop = signal("cmd_prop_chaged")
        self.lm = threading.Thread(
            target=self.thread_listen_process_cmd,
            name='listen_process_cmd',
            daemon=True
        )
        self.lm.start()
        self.sig_cmd_prop.connect(self.subscr_listen_process_cmd)

        self.sig_mpv_time = signal("mpv_time")

        self.sig_mpv_time_remain = signal("mpv_time_remain")
        self.sig_mpv_time_remain.connect(self.subscr_time)

        # will be replaced by options of optparse
        self.logger.info("Recived Keyargs: {}".format(args))
        print(type(self.logger))

        config = vctools.read_yaml()
        self.restart_at_error = config.get("restart_at_error")

        if len(args) > 2:
            try:
                arg_path = os.path.abspath(args[1])
            except OSError:
                arg_path = None
        else:
            arg_path = None   

        if arg_path:
            self.project_folder = arg_path
            self.logger.info("Project Folder From Argv: {}".format(self.project_folder))
        else:
            self.project_folder = config.get('media_file_path')
            self.logger.warning("Loaded filepath from config file: {}".format(self.project_folder))

        if len(args) == 3 and args[2] == "widescreen":
            self.content_aspect = "widescreen"
        else:
            self.content_aspect = "cinescope"
        self.logger.info("Aspect Ratio of content is {}.".format(self.content_aspect))
        
        if len(args) == 4:
            self.screen_id = int(args[3])
        else:
            self.screen_id = 10
        self.logger.info("Screen ID is {}.".format(self.screen_id))

        modules=["CommandDenon", "CommandAtlona"]
        modules=list()
        if ViewControl.multiprocess:
            self.process_cmd = multiprocessing.Process(
                target=CommandProcess.command_process, 
                name="process_cmd", 
                args=(self.config_queue_logger, 
                    self.command_queue, 
                    self.status_queue, 
                    modules),
                daemon=True)
            
            self.process_mpv = ProcessMpv(self.config_queue_logger,
                    self.mpv_status_queue, 
                    self.mpv_controll_queue,)
        else:
            self.process_cmd = threading.Thread(
                target=CommandProcess.command_process, 
                name="process_cmd", 
                args=(self.logger, self.command_queue, self.status_queue, modules),
                daemon=True)
            
            self.process_mpv = ThreadMpv(self.logger,
                    self.mpv_status_queue, 
                    self.mpv_controll_queue,)
            

        self.processeses = []
        self.processeses.append(self.process_cmd)
        self.processeses.append(self.process_mpv)

        self.logger.info("Initialized __main__ with pid {}".format(os.getpid()))


        self.event_next_happend = threading.Event()
        self.event_append = threading.Event()

    def main(self):

        for process in self.processeses:
            process.start()

        self.playlist = show.Show('testing', project_folder=self.project_folder)
        self.playlist.load_show()

        self.logger.info("loaded Show: {}".format(self.playlist.sequence_name))

        self.player_append_current_from_playlist()

        while True:
            self.event_append.wait()  # not bloking with if .is_set()
            self.player_append_next_from_playlist()
            self.event_append.clear()

    def player_append_next_from_playlist(self):
        self.player_append_element(self.playlist.next())
    
    def player_append_current_from_playlist(self):
        self.player_append_element(self.playlist.current_element)

    def player_append_element(self, element):
        print(type(element))
        if isinstance(element.media_element, show.StillElement):
            self.mpv_controll_queue.put((element.media_element.file_path_w, element.time))
        else:
            self.mpv_controll_queue.put((element.media_element.file_path_w, None))

    def subscr_time(self, time):
        print(self.event_next_happend.is_set(), time)
        if self.event_next_happend.is_set() and time and time < 1:
            self.event_next_happend.clear()
            self.event_append.set()

    def subscr_listen_process_mpv(self, msg):
        self.logger.debug("'mpv_prop_chaged' send: {}".format(msg))
        if msg[0] == 'playlist-pos' and self.playlist:
            self.duration = self.playlist.current_element.time
            self.event_next_happend.set()
    
    def thread_listen_process_mpv(self):
        while True:
            data = self.mpv_status_queue.get(block=True)
            if data[0] == 'time-pos':
                self.sig_mpv_time.send(data[1])
            elif data[0] == 'time-remaining':
                self.sig_mpv_time_remain.send(data[1])
                #self.logger.debug(data[1])
            else:
                self.sig_mpv_prop.send(data)

    def subscr_listen_process_cmd(self, msg):
        self.logger.debug("'cmd_prop_chaged' send: {}".format(msg))
    
    def thread_listen_process_cmd(self):
        while True:
            data = self.status_queue.get(block=True)
            self.sig_cmd_prop.send(data)

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """
        exeption handler to log unhandled expetions in main thread
        """
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        if not "Uncaught exception in subprocess:" in str(exc_value):
            self.logger.error(
                "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        #for p in multiprocessing.active_children():
        #    p.terminate()
        if False:#self.restart_at_error:
            self.logger.warning("Restarting Programm")
            os.execv(sys.executable, ['python3'] + sys.argv)
        else:
            self.logger.error("Exiting Programm")
            sys.exit()  # TODO not working

    def thread_logger(self, q):
        """
        thread running in main process handling all logging massages from
        the logging queue
        @param q: logger queue
        @type q: multiprocesssing.Queue
        """
        while True:
            record = q.get()
            if record is None:
                break
            logger = logging.getLogger(record.name)
            logger.handle(record)