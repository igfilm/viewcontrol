import argparse
import logging
import logging.config
import logging.handlers
import multiprocessing
import os
import queue
import sys
import threading
import time

import yaml
from blinker import signal

# run in headless environment (will be useful when adding video stream support)
if os.name == "posix" and "DISPLAY" in os.environ:
    from pynput import keyboard

import viewcontrol.show as show
from viewcontrol.playback.processmpv import ProcessMpv, ThreadMpv
from viewcontrol.remotecontrol.processcmd import ProcessCmd, ThreadCmd
from viewcontrol.remotecontrol.threadcommunicationbase import ComPackage
from viewcontrol.version import __version__ as package_version


class ViewControl(object):
    """ViewControl class.

    See README.rst for detailed module description.

    """

    def __init__(self, args):
        """Create a ViewControl object with the given options.

        Args:
            args (:list: string):
        """
        print(args)
        parser = argparse.ArgumentParser(
            prog="viewcontrol", description="media playback", epilog="to be filled"
        )
        parser.add_argument(
            "project_folder",
            help="folder path of project containing db-files and media-files",
        )
        parser.add_argument(
            "--show",
            action="store",
            dest="playlist_name",
            help="initial show to load (use full as long no GUI exists)",
        )
        parser.add_argument(
            "-r",
            "--content_aspect_ratio",
            action="store",
            choices=["c", "cinemascope", "21:9", "w", "widescreen", "16:9"],
            help="initial content aspect ratio of movie played by player",
        )
        parser.add_argument(
            "-s",
            "--screen",
            action="store",
            default=1,
            type=int,
            help="screen number/id for media playback",
        )
        parser.add_argument(
            "--threading",
            action="store_true",
            help="run program only with threading instead of multiprocessing",
        )
        parser.add_argument("--version", action="version", version=package_version)
        self.argpars_result = parser.parse_args(args[1:])
        self.argpars_result.project_folder = os.path.expanduser(
            self.argpars_result.project_folder
        )

        # Loading Logger with Configuration File
        logger_config_path = "logging.yaml"
        if os.path.exists(logger_config_path):
            with open(logger_config_path, "rt") as f:
                config_log = yaml.safe_load(f.read())
                for handler in config_log.get("handlers").values():
                    if "filename" in handler.keys():
                        dir_log = os.path.dirname(handler.get("filename"))
                        if not os.path.exists(dir_log):
                            os.makedirs(dir_log)
            logging.config.dictConfig(config_log)
        else:
            logging.basicConfig(level=logging.INFO)

        self.logger = logging.getLogger(threading.current_thread().name)
        self.logger.info("##################################")
        self.logger.info(
            "Program start with command line options: {}".format(
                str(self.argpars_result)
            )
        )

        # Add logging with traceback for all unhandled exceptions in
        # main thread
        sys.excepthook = self.handle_exception

        # Queue to enable logging from processes to one single file
        if not self.argpars_result.threading:
            q = multiprocessing.Queue()
        else:
            q = queue.Queue()
        self.config_queue_logger = {
            "version": 1,
            "disable_existing_loggers": True,
            "handlers": {
                "queue": {"class": "logging.handlers.QueueHandler", "queue": q},
            },
            "root": {"level": "DEBUG", "handlers": ["queue"]},
        }

        # Create and Start thread_logger
        self.lp = threading.Thread(
            target=self.thread_logger, args=(q,), name="thread_logger", daemon=True
        )
        self.lp.start()
        self.logger.info("Started '{}' with pid 'N.A.'".format(self.lp.name,))

        if not self.argpars_result.threading:
            self.cmd_control_queue = multiprocessing.Queue()
            self.cmd_status_queue = multiprocessing.Queue()
            self.mpv_control_queue = multiprocessing.Queue()
            self.mpv_status_queue = multiprocessing.Queue()
        else:
            self.cmd_control_queue = queue.Queue()
            self.cmd_status_queue = queue.Queue()
            self.mpv_control_queue = queue.Queue()
            self.mpv_status_queue = queue.Queue()

        # setup event mpv
        self.sig_mpv_prop = signal("mpv_prop_changed")
        self.t_listen_process_mpv = threading.Thread(
            target=self.thread_listen_process_mpv,
            name="listen_process_mpv",
            daemon=True,
        )
        self.t_listen_process_mpv.start()
        self.sig_mpv_prop.connect(self.subscr_listen_process_mpv)

        # setup event cmd
        self.sig_cmd_prop = signal("cmd_prop_changed")
        self.t_listen_process_cmd = threading.Thread(
            target=self.thread_listen_process_cmd,
            name="listen_process_cmd",
            daemon=True,
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
            target=self.thread_event_system, name="event_system", daemon=True
        )
        self.t_event_system.start()

        self.playlist = show.Show(
            project_folder=self.argpars_result.project_folder,
            content_aspect_ratio=self.argpars_result.content_aspect_ratio,
        )
        logging.info(
            "Connected to database: {}".format(self.playlist.connected_datbase)
        )
        self.playlist.show_load(self.argpars_result.playlist_name)
        self.logger.info("loaded Show: {}".format(self.playlist.show_name))

        if not self.argpars_result.threading:
            self.process_cmd = ProcessCmd(
                self.config_queue_logger,
                self.cmd_status_queue,
                self.cmd_control_queue,
                self.playlist.show_options.devices,
            )

            self.process_mpv = ProcessMpv(
                self.config_queue_logger,
                self.mpv_status_queue,
                self.mpv_control_queue,
                self.argpars_result.screen,
            )
        else:
            self.process_cmd = ThreadCmd(
                self.logger,
                self.cmd_status_queue,
                self.cmd_control_queue,
                self.playlist.show_options.devices,
            )

            self.process_mpv = ThreadMpv(
                self.logger,
                self.mpv_status_queue,
                self.mpv_control_queue,
                self.argpars_result.screen,
            )

        self.processes = []
        self.processes.append(self.process_cmd)
        self.processes.append(self.process_mpv)

        self.logger.info("Initialized __main__ with pid {}".format(os.getpid()))

        # blocking functions for appending next element to mpv playlist
        self.event_next_happened = threading.Event()
        self.event_append = threading.Event()

        # player currently playing media or is paused
        self.playing = threading.Event()
        self.playing.set()

        if "pyinput" not in sys.modules:
            # listen to all keypress events
            listener = keyboard.Listener(
                on_press=self.on_press, on_release=self.on_release
            )
            listener.setName("key_listener")
            listener.setDaemon(True)
            listener.start()

    def main(self):
        """
        entry point of program

        starts all in init initialized processes
        """

        for process in self.processes:
            process.start()

        time.sleep(1)

        self.player_append_current_from_playlist()
        for c in self.playlist.module_current.list_commands:
            self.sig_cmd_command.send(c)

        while True:
            self.event_append.wait()  # not blocking with if .is_set()
            self.player_append_next_from_playlist()
            self.event_append.clear()
            self.event_next_happened.wait()
            for c in self.playlist.module_current.list_commands:
                self.sig_cmd_command.send(c)

    def send_command(self, command_obj):
        """send command object to process/thread: process_cmd

        Args:
            command_obj  (show.CommandObject): objected containing
                command details

        """
        self.logger.info("Sending CommandObject '{}'".format(command_obj))
        self.cmd_control_queue.put(command_obj)

    def player_resume(self):
        """resume playback and timers

        resumes playback of video and delay timer,
        being paused by player_pause.

        """
        if not self.playing.is_set():
            self.playing.set()
            self.mpv_control_queue.put("resume")
            self.cmd_control_queue.put("resume")

    def player_pause(self):
        """pause playback and timers

        pauses playback and delay timers until,
        released by resume_playback.

        """
        if self.playing.is_set():
            self.playing.clear()
            self.mpv_control_queue.put("pause")
            self.cmd_control_queue.put("pause")

    def player_toggle_play_pause(self):
        """toggle playback and timers

        pause or resume playback depending on the current condition.

        """
        if self.playing.is_set():
            self.player_pause()
        else:
            self.player_resume()

    def player_append_next_from_playlist(self):
        """Append next playlist element to player

        loads next playable element from playlist (show.Show) calling
        'player_append_element'.

        """
        self.player_append_element(self.playlist.next())

    def player_append_current_from_playlist(self):
        """Append current playlist element to player

        loads current playable element from playlist (show.Show) calling
        'player_append_element'.

        """
        self.player_append_element(self.playlist.module_current)

    def player_append_element(self, element):
        """Append SequenceElement to player

        sends media file of given element to playback process/thread
        (playback.processmpv). Also sends user defined display duration,
        if the media type got no predefined duration, which is the case
        which is the case with all show.StillElement where a
        user-defined time is stored.

        """
        if isinstance(element.media_element, show.StillElement) or isinstance(
            element.media_element, show.TextElement
        ):
            self.mpv_control_queue.put((element.media_element.file_path, element.time))
        else:
            self.mpv_control_queue.put((element.media_element.file_path, None))

    def subscr_time(self, remaining_time):
        """Blinker-Event subscriber: remaining playtime of media element

        Set and delete threading.events which are used to synchronize
        playlist changes with the mpv-player and control process.

        Responds to the remaining time of the current media element and
        allows you to add the next element.

        """
        if self.event_next_happened.is_set() and remaining_time and remaining_time < 1:
            self.event_next_happened.clear()
            self.event_append.set()

    def subscr_listen_process_mpv(self, msg):
        """Blinker-Event subscriber: change of media element in player

        Set and delete threading.events which are used to synchronize
        playlist changes with the mpv-player and control process.

        Responds to the remaining time of the current media element and
        allows you to add the next element.

        detects the current change of the media element in the mpv-player
        and enables the sending of the commands or the starting of the
        delay timer.

        """
        self.logger.debug("'mpv_prop_changed' send: {}".format(msg))
        if msg[0] == "playlist-pos" and self.playlist:
            self.event_next_happened.set()

    def thread_listen_process_mpv(self):
        """Thread: forward status information of process_mpv ...

        to Blinker-Event. Blinker-Event defined in init.

        """
        while True:
            data = self.mpv_status_queue.get(block=True)
            if data[0] == "time-pos":
                self.sig_mpv_time.send(data[1])
            elif data[0] == "time-remaining":
                self.sig_mpv_time_remain.send(data[1])
                self.logger.debug(data[1])
            else:
                self.sig_mpv_prop.send(data)

    def subscr_listen_process_cmd(self, msg):
        """Blinker-Event subscriber: all received communication

        Log all received communication data. Blinker-Event defined in
        init.

        """
        self.logger.debug("'cmd_prop_changed' send: {}".format(msg))

    def thread_listen_process_cmd(self):
        """Thread: forward status information and received messages ...

        of processcmd to Blinker-Event (general availability and logging)
        and self.event_queue (handling events). Blinker-Event defined
        in init.

        """
        while True:
            data = self.cmd_status_queue.get(block=True)
            self.sig_cmd_prop.send(data)
            self.event_queue.put(data)

    if "pyinput" not in sys.modules:

        def thread_event_system(self):
            """Thread: event system for user defined events

            compares every received communication package with user defined
            event list. If event matches, run/trigger in show.EventModule
            specified action.

            """
            while True:
                data = self.event_queue.get(block=True)
                if isinstance(data, ComPackage):  # ComEvent
                    etype = show.ComEventModule
                elif isinstance(data, tuple) and data[0] == "KeyEvent":  # KeyEvent
                    etype = show.KeyEventModule
                else:
                    return
                for mod in self.playlist.eventlist:
                    if isinstance(mod, etype):
                        if mod.check_event(data):
                            for cmd_tpl in mod.list_commands:
                                self.sig_cmd_command.send(cmd_tpl)
                            if mod.jump_to_target_element:
                                self.playlist.notify(mod.jump_to_target_element)

        def on_press(self, key):
            """pynput event listener: key event on press"""
            try:
                self.logger.debug("alphanumeric key {0} pressed".format(key))
            except AttributeError:
                self.logger.debug("special key {0} pressed".format(key))

            if key == keyboard.Key.page_down:
                self.player_pause()
            elif key == keyboard.Key.page_up:
                self.player_resume()

            self.event_queue.put(("KeyEvent", key, "on_press"))

    def on_release(self, key):
        """pynput event listener: key event on release"""
        self.event_queue.put(("KeyEvent", key, "on_release"))

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """Exception handler to log unhandled exceptions in main thread

        Logs exception including traceback to logfile and exits program.

        """
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        if "Uncaught exception in subprocess:" not in str(exc_value):
            self.logger.error(
                "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
            )

        self.logger.error("Exiting Program")
        sys.exit()  # TODO not working

    @staticmethod
    def thread_logger(q):
        """Thread: Handle logging of processes

        Running in main process handling all logging massages from the
        logging queue

        Args:
        q        (multiprocesssing.Queue): logger queue

        """
        while True:
            record = q.get()
            if record is None:
                break
            logger = logging.getLogger(record.name)
            logger.handle(record)
