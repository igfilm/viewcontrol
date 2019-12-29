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
from viewcontrol.remotecontrol.processcmd import ProcessCmd, ThreadCmd
from viewcontrol.remotecontrol.threadcommunicationbase import ComPackage
from viewcontrol.playback.processmpv import ProcessMpv, ThreadMpv

from viewcontrol.version import __version__ as package_version

class ViewControl(object):

    def __init__(self, args):
        print(args)
        parser = argparse.ArgumentParser(
            prog = "viewcontrol",
            description='media playback',
            epilog='fuubar')
        parser.add_argument('project_folder',
            help="folder path of project containing db-files and media-files")
        parser.add_argument('--show', 
            action='store',
            dest='playlist_name',
            help="inital show to load (usefull as long no GUI exists)")
        parser.add_argument('-r', '--content_aspect_ratio', 
            action='store', 
            choices=['c', 'cinescope', '21:9', 'w', 'widescreen', '16:9'],
            help="initial content aspect ratio of movie played by BluRay-Player")
        parser.add_argument('-s', '--screen', 
            action='store', 
            default=1, 
            type=int,
            help="screen number/id for media playback")
        parser.add_argument('--threading', 
            action='store_true',
            help='run programm only with threading intead of multiprocesing')
        parser.add_argument('--version', action='version', version=package_version)
        self.argpars_result = parser.parse_args(args[1:])
        self.argpars_result.project_folder = os.path.expanduser(self.argpars_result.project_folder)

        #Loading Logger with Configutation File
        logger_config_path = 'logging.yaml'
        if os.path.exists(logger_config_path):
            with open(logger_config_path, 'rt') as f:
                config_log = yaml.safe_load(f.read())
                for handler in config_log.get('handlers').values():
                    if 'filename' in handler.keys():
                        dir_log = os.path.dirname(handler.get("filename"))
                        if not os.path.exists(dir_log):
                            os.makedirs(dir_log)
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
        self.t_listen_process_mpv = threading.Thread(
            target=self.thread_listen_process_mpv,
            name='listen_process_mpv',
            daemon=True
        )
        self.t_listen_process_mpv.start()
        self.sig_mpv_prop.connect(self.subscr_listen_process_mpv)

        # setup event cmd
        self.sig_cmd_prop = signal("cmd_prop_chaged")
        self.t_listen_process_cmd = threading.Thread(
            target=self.thread_listen_process_cmd,
            name='listen_process_cmd',
            daemon=True
        )
        self.t_listen_process_cmd.start()
        self.sig_cmd_prop.connect(self.subscr_listen_process_cmd)

        self.sig_mpv_time = signal("mpv_time")
        self.sig_mpv_time_remain = signal("mpv_time_remain")
        self.sig_mpv_time_remain.connect(self.subscr_time)

        self.sig_cmd_command = signal("cmd_command")
        self.sig_cmd_command.connect(self.send_command)

        self.event_queue = queue.Queue()
        self.t_event_system = threading.Thread(
            target=self.thread_event_system,
            name='event_system',
            daemon=True
        )
        self.t_event_system.start()

        self.playlist = show.Show(
            project_folder=self.argpars_result.project_folder, 
            content_aspect_ratio=self.argpars_result.content_aspect_ratio)
        logging.info("Connected to database: {}".format(self.playlist.connected_datbase))
        self.playlist.show_load(self.argpars_result.playlist_name)
        self.logger.info("loaded Show: {}".format(self.playlist._show_name))

        if not self.argpars_result.threading:
            self.process_cmd = ProcessCmd(self.config_queue_logger, 
                    self.cmd_status_queue, 
                    self.cmd_controll_queue, 
                    self.playlist.show_options.devices)
            
            self.process_mpv = ProcessMpv(self.config_queue_logger,
                    self.mpv_status_queue,
                    self.mpv_controll_queue,
                    self.argpars_result.screen)
        else:
            self.process_cmd = ThreadCmd(self.logger, 
                self.cmd_status_queue,
                self.cmd_controll_queue,
                self.playlist.show_options.devices)
            
            self.process_mpv = ThreadMpv(self.logger,
                    self.mpv_status_queue, 
                    self.mpv_controll_queue,
                    self.argpars_result.screen)
            
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

        time.sleep(1)

        self.player_append_current_from_playlist()
        for c in self.playlist.module_current.list_commands:
            self.sig_cmd_command.send(c)

        while True:
            self.event_append.wait()  # not bloking with if .is_set()
            self.player_append_next_from_playlist()
            self.event_append.clear()
            self.event_next_happend.wait()
            for c in self.playlist.module_current.list_commands:
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
        self.player_append_element(self.playlist.module_current)

    def player_append_element(self, element):
        """Append SequenceElement to player"""
        if isinstance(element.media_element, show.StillElement) \
                or isinstance(element.media_element, show.TextElement):
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
                self.logger.debug(data[1])
            else:
                self.sig_mpv_prop.send(data)
                #self.event_queue.put(data)

    def subscr_listen_process_cmd(self, msg):
        """Subscriber to Event 'cmd_prop_chaged' for logging."""
        self.logger.debug("'cmd_prop_chaged' send: {}".format(msg))
    
    def thread_listen_process_cmd(self):
        """Thread listenig to command Queue. Forwards Recived data as Event"""
        while True:
            data = self.cmd_status_queue.get(block=True)
            self.sig_cmd_prop.send(data)
            self.event_queue.put(data)

    def thread_event_system(self):
        """fuubar"""
        while True:
            data = self.event_queue.get(block=True)
            etype = None
            if isinstance(data, ComPackage):  # ComEvent
                etype = show.ComEventModule
            elif isinstance(data, tuple) and data[0]=="KeyEvent":  # KeyEvent
                etype = show.KeyEventModule
            else:
                print("fuubar")
            for mod in self.playlist.eventlist:
                if isinstance(mod, etype):
                    if mod.check_event(data):
                        for cmd_tpl in mod.list_commands:
                            self.sig_cmd_command.send(cmd_tpl)
                        if mod.jump_to_target_element:
                            self.playlist.notify(mod.jump_to_target_element)
                        #send commads
                        #notifie jump to element

    def on_press(self, key):
        """key event on press
        
        TODO add move pause resume to event system
        """
        try:
            self.logger.debug('alphanumeric key {0} pressed'.format(key))
        except AttributeError:
            self.logger.debug('special key {0} pressed'.format(key))

        if key == keyboard.Key.page_down:
            self.player_pause()
        elif key == keyboard.Key.page_up:
            self.player_resume()
        
        self.event_queue.put(("KeyEvent", key, "on_press"))

    def on_release(self, key):
        """key event on release"""
        self.event_queue.put(("KeyEvent", key, "on_release"))

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