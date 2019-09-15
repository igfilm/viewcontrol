import multiprocessing
import threading
import time
import logging
import logging.config
import logging.handlers
import os
import sys
import yaml


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

        config_path = "config.yaml"
        if os.path.exists(config_path):
            with open(config_path, 'rt') as f:
                config = yaml.safe_load(f.read())
                self.restart_at_error = config.get("restart_at_error")
        else:
            raise FileNotFoundError(
                "Config File {} not found, can't start programm!" \
                .format(os.path.abspath(config_path)))

        self.processA = multiprocessing.Process(target=self.process_A, name="processA", args=(self.config_queue_logger,) )
        self.processA.daemon = True

        self.processB = multiprocessing.Process(target=self.process_B, name="processB", args=(self.config_queue_logger,) )
        self.processB.daemon = True

        self.processeses = []
        self.processeses.append(self.processA)
        self.processeses.append(self.processB)

    def process_A(self, logger_config):
        logging.config.dictConfig(logger_config)
        logger = logging.getLogger("process_A")
        logger.info("Started process_A")
        try:
            while True:
                time.sleep(1)
                logger.debug("Hello")
                time.sleep(5)
                raise RuntimeError("Test unhandled")
        except Exception as e:
            try:
                raise
            finally:
                logger.error("Uncaught exception", exc_info=(e))    

    def process_B(self, logger_config):
        logging.config.dictConfig(logger_config)
        logger = logging.getLogger("process_B")
        logger.info("Started process_B")
        try:
            while True:
                time.sleep(1)
                logger.debug("World")
        except Exception as e:
            try:
                raise
            finally:
                logger.error("Uncaught exception", exc_info=(e))

    def run(self):
        self.logger.info("StartedingProcessses")
        for process in self.processeses:
            process.start()
        while True:
            for process in self.processeses:
                if not process.is_alive():
                    exc_msg = "Uncaught exception in subprocess: '{}'".format(process.name)
                    self.logger.error(exc_msg)
                    for p in multiprocessing.active_children():
                        p.terminate()
                    raise Exception(exc_msg)

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
