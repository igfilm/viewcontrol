import multiprocessing
import threading
import time
import logging
import logging.config
import logging.handlers
import os
import sys
import yaml

import sqlalchemy
from sqlalchemy import create_engine

import functools

import vctools
from vctools import read_yaml
import mediaelement

import mpv

import mediaelement
from mediaelement import MediaElement, VideoElement, StillElement, Command
from remotec.commandprocess import CommandProcess

class ViewControl(object):

    def __init__(self, default_config_yaml_path='config.yaml'):
      
        # Set the path to the path where the script resides
        abspath = os.path.abspath(__file__)
        dname = os.path.dirname(abspath)
        os.chdir(dname)

        #Loading Logger with Configutation File
        logger_config_path = 'logging.yaml'
        if os.path.exists(logger_config_path):
            with open(logger_config_path, 'rt') as f:
                config = yaml.safe_load(f.read())
            logging.config.dictConfig(config)
        else:
            logging.basicConfig(level=logging.INFO)

        self.logger = logging.getLogger(__name__)

        #Add logging with traceback for all unhandled exeptions in main thread
        #https://stackoverflow.com/questions/6234405/
        #    logging-uncaught-exceptions-in-python/16993115#16993115
        handler = logging.StreamHandler(stream=sys.stdout)
        self.logger.addHandler(handler)
        sys.excepthook = self.handle_exception

        # Queue for the logger to enable logging from proscesses to
        # one single file
        q = multiprocessing.Queue()
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

        lp = threading.Thread(target=self.logger_thread, args=(q,))
        lp.start()

        config = vctools.read_yaml()
        self.restart_at_error = config.get("restart_at_error")
        self.media_file_path = config.get('media_file_path')
        
        self.pipe_mpv_stat_A, self.pipe_mpv_stat_B = multiprocessing.Pipe()
        self.mpv_controll_queue = multiprocessing.Queue()

        pipeA, pipeB = multiprocessing.Pipe()

        self.process_cmd = multiprocessing.Process(
            target=CommandProcess.command_process, 
            name="process_cmd", 
            args=(pipeB, self.logger))
        self.process_cmd.daemon = True

        self.process_mpv = multiprocessing.Process(
            target=self.def_process_mpv, 
            name="process_mpv", 
            args=(self.config_queue_logger,
                self.pipe_mpv_stat_B, 
                self.mpv_controll_queue,))
        self.process_mpv.daemon = True

        self.processeses = []
        if config.get('use_communication'):
            self.processeses.append(self.process_cmd)
        else:
            #process or funtion to empty pipes?
            pass
        self.processeses.append(self.process_mpv)

        self.logger.info("Initialized __main__ with pid {}".format(os.getpid()))

        self.playlist = mediaelement.Show('testing')
        self.playlist.load_show()
        self.element_current = None
        self.element_next = None

        #Only For Pre-Alpha Version
        t = threading.Thread(
            target=ViewControl.wait_for_enter, 
            name='pre-alpha', 
            args=(pipeA,))
        t.start()

    #Only For Pre-Alpha Version
    @staticmethod
    def wait_for_enter(pipeA):
        input("Press Enter to Start BluRay")
        pipeA.send("start")

    def mpv_log(self, loglevel, component, message, log):
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
        log.log(level, "MPV:" + message)

    def mpv_observer_stat(self, prop, value, log, pipe):
            pipe.send((prop, value))

    def def_process_mpv(self, logger_config, pipe_mpv_statl, queue_mpv):
        logging.config.dictConfig(logger_config)
        logger = logging.getLogger("process_mpv")
        logger.info("Started process_mpv with pid {}".format(os.getpid()))
        
        try:
            # mpv expects logger func without a logger, therfore create new funtion
            # with log already filled in  
            mpv_log = functools.partial(self.mpv_log, log=logger)

            #initilaize player
            player = mpv.MPV(log_handler=mpv_log, ytdl=False)
            player.fullscreen = True
            player['image-display-duration'] = 100  # Pipe in while loop to update duration
            player['keep-open'] = True
            player['osc'] = False

            handler_mpv_observer_stat = functools.partial(self.mpv_observer_stat, log=logger, pipe=pipe_mpv_statl)
            player.observe_property('filename', handler_mpv_observer_stat)

            #first immage to avoid idle player
            player.playlist_append('viewcontrol.png')

            while True:

                # wait for data in queue, add file to playlist when data is
                # type str. Otherwse jump to next track (only used with still)
                if not queue_mpv.empty():
                    data = queue_mpv.get()
                    if isinstance(data, str):                
                        player.playlist_append(data)
                        logger.info("Appending File {} at pos {} in playlist.".format(str(data), len(player.playlist)))
                    else:
                        player.playlist_next()
                        logger.info("Call playlist_next")
                
        except Exception as e:
            try:
                raise
            finally:
                logger.error("Uncaught exception", exc_info=(e))

    def timer_action_next(self):
        self.logger.error("Timer Next Action")
        self.mpv_controll_queue.put(None)

    def timer_append_next(self, path):
        self.logger.error("Timer Next Append")
        self.mpv_controll_queue.put(path)

    def run(self):
        self.logger.info("StartedingProcessses")
        for process in self.processeses:
            process.start()

        self.playlist = mediaelement.Show('testing')
        self.playlist.load_show()

        while True:
                     
            if self.pipe_mpv_stat_A.poll():
                data = self.pipe_mpv_stat_A.recv()
                if data[0] == 'filename':
                    self.logger.error("recived filename {}".format(data))
                    self.element_next = self.playlist.next()
                    if True:
                        file_path_next = self.element_next.media_element.file_path_w
                    else:
                        file_path_next = self.element_next.media_element.file_path_c
                    time = self.element_next.time
                    threading.Timer(time-1, self.timer_append_next, args=(file_path_next,)).start()
                    if isinstance(self.element_next.media_element, StillElement):
                        threading.Timer(time, self.timer_action_next).start()

            for process in self.processeses:
                if not process.is_alive():
                    exc_msg = "Uncaught exception in subprocess: '{}'".format(process.name)
                    
                    if self.restart_at_error:
                        process.terminate()
                        process.start()
                        str.join(exc_msg, "Restarting Processes")
                    else:
                        str.join(exc_msg, "Terminate all Processes")
                        for p in multiprocessing.active_children():
                            p.terminate()
                        raise Exception(exc_msg)
                    
                    self.logger.error(exc_msg)


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
        if self.restart_at_error:
            self.logger.warning("Restarting Programm")
            os.execv(sys.executable, ['python3'] + sys.argv)
        else:            
            self.logger.warning("Exiting Programm")
            sys.exit()  # TODO not working

    def logger_thread(self, q):
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


  
if __name__ == "__main__":
    test = ViewControl()
    test.run()
