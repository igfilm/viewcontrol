import multiprocessing
import threading
import queue
import time
import logging
import logging.config
import logging.handlers
import os
import sys
import argparse
import yaml

from blinker import signal
from pynput import keyboard

import functools

import mpv

import viewcontrol.show as show
from viewcontrol.remotec.processcmd import ProcessCmd, ThreadCmd
from viewcontrol.playback.processmpv import ProcessMpv, ThreadMpv

from viewcontrol.version import __version__ as package_version

class ViewControl(object):

    def __init__(self, args):

        parser = argparse.ArgumentParser(
            description='media playback',
            epilog='fuubar')
        parser.add_argument('project_folder',
            help="folder path of project containing db-files and media-files")
        parser.add_argument('-r', '--content_aspect_ratio', 
            action='store', 
            choices=['c', 'cinescope', '21:9', 'w', 'widescreen', '16:9'],
            help="sontent aspect ratio of movie played by BluRay-Player")
        parser.add_argument('-s', '--screen', 
            action='store', 
            default=42, 
            type=int,
            help="screen number/id for media playback")
        parser.add_argument('-m', '--modules', 
            action='store', 
            nargs='*', 
            default=None,
            help="")
        parser.add_argument('--threading', 
            action='store_true',
            help='run programm only with threading intead of multiprocesing')
        parser.add_argument('--version', action='version', version=package_version)
        self.argpars_result = parser.parse_args(args[1:])

        #Loading Logger with Configutation File
        logger_config_path = 'logging.yaml'
        if os.path.exists(logger_config_path):
            with open(logger_config_path, 'rt') as f:
                config_log = yaml.safe_load(f.read())
            logging.config.dictConfig(config_log)
        else:
            logging.basicConfig(level=logging.INFO)

        self.logger = logging.getLogger(threading.current_thread().name)
        self.logger.info("##################################")
        self.logger.info("Program start with command line options: {}".
            format(str(self.argpars_result)))

        #Add logging with traceback for all unhandled exeptions in main thread
        sys.excepthook = self.handle_exception

        # Queue to enable logging from proscesses to one single file
        if not self.argpars_result.threading:
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

        if not self.argpars_result.threading:
            self.cmd_controll_queue = multiprocessing.Queue()
            self.cmd_status_queue = multiprocessing.Queue()
            self.mpv_controll_queue = multiprocessing.Queue()
            self.mpv_status_queue = multiprocessing.Queue()
        else:
            self.cmd_controll_queue = queue.Queue()
            self.cmd_status_queue = queue.Queue()
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

        self.sig_cmd_command = signal("cmd_command")
        self.sig_cmd_command.connect(self.send_command)

        if not self.argpars_result.modules:
            modules = ["CommandDenon", "CommandAtlona"]
        else:
            modules = self.argpars_result.modules

        if not self.argpars_result.threading:
            self.process_cmd = ProcessCmd(self.config_queue_logger, 
                    self.cmd_status_queue, 
                    self.cmd_controll_queue, 
                    modules)
            
            self.process_mpv = ProcessMpv(self.config_queue_logger,
                    self.mpv_status_queue, 
                    self.mpv_controll_queue,)
        else:
            self.process_cmd = ThreadCmd(self.logger, 
                self.cmd_status_queue,
                self.cmd_controll_queue,
                modules)
            
            self.process_mpv = ThreadMpv(self.logger,
                    self.mpv_status_queue, 
                    self.mpv_controll_queue,)
            
        self.processeses = []
        self.processeses.append(self.process_cmd)
        self.processeses.append(self.process_mpv)

        self.logger.info("Initialized __main__ with pid {}".format(os.getpid()))

        # blocking funtions for appending next eleement to player playlist
        self.event_next_happend = threading.Event()
        self.event_append = threading.Event()

        # player currently playing media or is paused
        self.playing = threading.Event()
        self.playing.set() 

        # dangerous, listen to all kexpresses. Event generator for Testing.
        listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release)
        listener.setName("key_listener")
        listener.setDaemon(True)
        listener.start() 


    def main(self):

        for process in self.processeses:
            process.start()

        self.playlist = show.Show('testing', 
            project_folder=self.argpars_result.project_folder, 
            content_aspect_ratio=self.argpars_result.content_aspect_ratio)

        self.logger.info("loaded Show: {}".format(self.playlist.sequence_name))

        self.player_append_current_from_playlist()
        for c in self.playlist.current_element.list_commands:
            self.sig_cmd_command.send(c)

        while True:
            self.event_append.wait()  # not bloking with if .is_set()
            self.player_append_next_from_playlist()
            self.event_append.clear()
            self.event_next_happend.wait()
            for c in self.playlist.current_element.list_commands:
                self.sig_cmd_command.send(c)

    def send_command(self, command_obj):
        self.logger.info("Sending Commandobject '{}'".format(command_obj))
        self.cmd_controll_queue.put(command_obj)

    def player_resume(self):
        """resume playback and timers"""
        if not self.playing.is_set():
            self.playing.set()
            self.mpv_controll_queue.put("resume")
            self.cmd_controll_queue.put("resume")

    def player_pause(self):
        """pause playback and timers"""
        if self.playing.is_set():
            self.playing.clear()
            self.mpv_controll_queue.put("pause")
            self.cmd_controll_queue.put("pause")

    def player_playpause(self):
        """toogle playback and timers"""
        if self.playing.is_set():
            self.player_pause()
        else:
            self.player_resume()

    def player_append_next_from_playlist(self):
        """Append next playlist element to player"""
        self.player_append_element(self.playlist.next())
    
    def player_append_current_from_playlist(self):
        """Append current playlist element to player"""
        self.player_append_element(self.playlist.current_element)

    def player_append_element(self, element):
        """Append SequenceElement to player"""
        if isinstance(element.media_element, show.StillElement):
            self.mpv_controll_queue.put((element.media_element.file_path, element.time))
        else:
            self.mpv_controll_queue.put((element.media_element.file_path, None))

    def subscr_time(self, time):
        """Function subscribed to remaining time, triggering player_append"""
        if self.event_next_happend.is_set() and time and time < 1:
            self.event_next_happend.clear()
            self.event_append.set()

    def subscr_listen_process_mpv(self, msg):
        """Function subscribed to property changes of player, sets 
            event_next_happend which used for synchronisation of playlist and
            player.
        """
        self.logger.debug("'mpv_prop_chaged' send: {}".format(msg))
        if msg[0] == 'playlist-pos' and self.playlist:
            self.event_next_happend.set()
    
    def thread_listen_process_mpv(self):
        """Thread listenig to player Queue. Forwards Recived data as Event"""
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
        """Subscriber to Event 'cmd_prop_chaged' for logging."""
        self.logger.debug("'cmd_prop_chaged' send: {}".format(msg))
    
    def thread_listen_process_cmd(self):
        """Thread listenig to command Queue. Forwards Recived data as Event"""
        while True:
            data = self.cmd_status_queue.get(block=True)
            self.sig_cmd_prop.send(data)

    def on_press(self, key):
        """key event on press"""
        try:
            self.logger.debug('alphanumeric key {0} pressed'.format(key))
        except AttributeError:
            self.logger.debug('special key {0} pressed'.format(key))
        #self.sig_key_event.send(key)
        if key == keyboard.Key.page_down:
            self.player_pause()
        elif key == keyboard.Key.page_up:
            self.player_resume()
        elif key == keyboard.Key.end:
            self.playlist.notify("start trailer")
            #self.player_playpause()

    def on_release(self, key):
        """key event on release"""
        pass

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """exeption handler to log unhandled expetions in main thread"""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        if not "Uncaught exception in subprocess:" in str(exc_value):
            self.logger.error(
                "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
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