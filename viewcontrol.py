import multiprocessing
import threading
import time
import logging
import logging.config
import logging.handlers
import os
import sys
import yaml

import functools

#from pynput.keyboard import Key, Listener

try: 
    import mpv
except OSError:
    print("libmpv not found please install. See debug log for traceback.")
    raise

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

        default_config_path = "config.yaml"
        if os.path.exists(default_config_path):
            with open(default_config_path, 'rt') as f:
                config = yaml.safe_load(f.read())
                self.restart_at_error = config.get("restart_at_error")
                self.media_file_path = config.get('media_file_path')
        else:
            raise FileNotFoundError(
                "Config File {} not found, can't start programm!" \
                .format(os.path.abspath(default_config_path)))

        

        #self.pipe_pc, self.pipe_cc = multiprocessing.Pipe()
        self.pipe_mpv_time_A, self.pipe_mpv_time_B = multiprocessing.Pipe()
        self.pipe_mpv_stat_A, self.pipe_mpv_stat_B = multiprocessing.Pipe()
        self.pipe_mpv_apnd_A, self.pipe_mpv_apnd_B = multiprocessing.Pipe()

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
                self.pipe_mpv_time_B, 
                self.pipe_mpv_stat_B, 
                self.pipe_mpv_apnd_A,))
        self.process_mpv.daemon = True

        self.processeses = []
        self.processeses.append(self.process_cmd)
        self.processeses.append(self.process_mpv)

        self.logger.info("Initialized __main__ with pid {}".format(os.getpid()))

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

    # def def_process_cmd(self, logger_config):
    #     """example process definition"""
    #     logging.config.dictConfig(logger_config)
    #     logger = logging.getLogger("process_A")
    #     logger.info("Started process_A with pid {}".format(os.getpid()))
    #     try:
    #         while True:
    #             time.sleep(1)
    #     except Exception as e:
    #         try:
    #             raise
    #         finally:
    #             logger.error("Uncaught exception", exc_info=(e))    

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


    def mpv_observer_time(self, prop, value, log, pipe):
            pipe.send((prop, value))


    def mpv_observer_stat(self, prop, value, log, pipe):
            pipe.send((prop, value))


    def def_process_mpv(self, logger_config, 
        pipe_mpv_time, pipe_mpv_statl, pipe_mpv_apnd):
        logging.config.dictConfig(logger_config)
        logger = logging.getLogger("process_mpv")
        logger.info("Started process_mpv with pid {}".format(os.getpid()))
        # mpv expects logger func without a logger, therfore create new funtion
        # with log already filled in  
        try:
            mpv_log = functools.partial(self.mpv_log, log=logger)
            player = mpv.MPV(log_handler=mpv_log, ytdl=False)
            player.fullscreen = True
            player['image-display-duration'] = 5  # Pipe in while loop to update duration
            player['keep-open'] = True
            player['osc'] = False
            #player.loop_playlist = 'inf'

            #handler_mpv_observer_time = functools.partial(self.mpv_observer_time, log=logger, pipe=pipe_mpv_time)
            #player.observe_property('time-remaining', handler_mpv_observer_time)
            #player.observe_property('time-pos', handler_mpv_observer_time)
            #handler_mpv_observer_stat = functools.partial(self.mpv_observer_stat, log=logger, pipe=pipe_mpv_statl)
            #player.observe_property('filename', handler_mpv_observer_stat)
            #player.observe_property('playlist', handler_mpv_observer_stat)
            #player.observe_property('playlist-pos', handler_mpv_observer_stat)
            #player.observe_property('playlist-pos-1', handler_mpv_observer_stat)
            #player.observe_property('playlist-count', handler_mpv_observer_stat)
            
            player.playlist_append('viewcontrol.png')
            #logger.info("disptime: {}".format(player['image-display-duration']))
            player.playlist_append('pic1_im_moon.jpg')
            player.playlist_append('pic2_im_pda.jpg')
            player.playlist_append('pic3_im_shark.jpg')

            while True:
                if pipe_mpv_apnd.poll():
                    data = pipe_mpv_apnd.recv()                   
                    player.playlist_append(data.file_path)
                    #if(isinstance(data, StillElement)):
                        #player['image-display-duration'] = data.display_time
                    logger.info("Appending File {} at pos {} in playlist.".format(str(data), len(player.playlist)))
                
        except Exception as e:
            try:
                raise
            finally:
                logger.error("Uncaught exception", exc_info=(e))

    def run(self):
        self.logger.info("StartedingProcessses")
        for process in self.processeses:
            process.start()

        # poped = False

        # pic1 = StillElement('pic1', 'pic1_im_moon.jpg', display_time=8)
        # pic2 = StillElement('pic2', 'pic2_im_pda.jpg', Command('Hello', 'World', 3), display_time=13)
        # pic3 = StillElement('pic3', 'pic3_im_shark.jpg', display_time=7)
        # pic4 = StillElement('pic4', 'pic4_IMG_3311.JPG', display_time=3)

        # vid1 = VideoElement('vid1', 'vid1_forever.mkv')
        # vid2 = VideoElement('vid2', 'vid2.mp4', Command('fuu', 'bar', 3))
        # vid3 = VideoElement('vid3', 'vid3.mp4', [Command('fuu2', 'bar2', 2), Command('fuu4', 'bar4', 4)])
        # vid4 = VideoElement('vid4', 'vid4_fire.mp4')
        
        # listloop = [vid2, pic1, pic2, pic3, pic4, ]

        # element_current = pic3
        # element_next = None
        # timerlist = None

        # while True:            
        #     if self.pipe_mpv_stat_A.poll():
        #         data = self.pipe_mpv_stat_A.recv()
        #         if data[0] == 'playlist-pos-1':
        #             self.logger.info("recived playlist pos {}".format(data))
        #             poped = False
        #         elif data[0] == 'filename':
        #             self.logger.info("recived filename {}".format(data))
        #             if data[1]=='viewcontrol.png':
        #                 print("fuu")
        #                 continue
        #             elif data[1]==element_next.file_path:
        #                 print("bar")             
        #                 element_current = element_next
        #                 timerlist = []
        #                 if element_current.list_commands:
        #                     for me in element_current.list_commands:
        #                         if me:
        #                             timerlist.append(threading.Timer(
        #                                 interval=me.delay, 
        #                                 function=self.runcommand, 
        #                                 args=(me.name, self.logger)))
        #                     for t in timerlist:
        #                         t.start()
        #     elif not poped and isinstance(element_current, StillElement):
        #         if len(listloop) > 0:
        #             media_element = listloop.pop(0)
        #             self.pipe_mpv_apnd_B.send(media_element)
        #             element_next = media_element
        #             poped = True
        #     elif self.pipe_mpv_time_A.poll():
        #         data = self.pipe_mpv_time_A.recv()
        #         #self.logger.debug("recived time {}".format(data))
        #         if not poped and len(listloop) > 0:
        #             if data[1] <= 1:
        #                 media_element = listloop.pop(0)
        #                 self.pipe_mpv_apnd_B.send(media_element)
        #                 element_next = media_element
        #                 poped = True
        #     #elif not element_next:
        #     #    if not poped and len(listloop) > 0:
        #     #        media_element = listloop.pop(0)
        #     #        self.pipe_mpv_apnd_B.send(media_element)
        #     #        element_next = media_element
        #     #        poped = True
            
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
                
                
            #time.sleep(.1)

        

    def runcommand(self, cmdobj, cmdqueue):
        cmdqueue.info("now command '{}' will be send to device".format(cmdobj))

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
