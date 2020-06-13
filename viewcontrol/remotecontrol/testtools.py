import logging
import logging.config
import logging.handlers
import multiprocessing
import queue
import sys
import threading
import tkinter as tk
import tkinter.ttk as tkk
from tkinter import scrolledtext

from viewcontrol.remotecontrol import supported_devices
from viewcontrol.remotecontrol.commanditem import CommandSendItem
from viewcontrol.remotecontrol.commanditem import format_arg_count
from viewcontrol.remotecontrol.processcmd import ThreadCmd
from viewcontrol.remotecontrol.processcmd import ProcessCmd


class Application(tk.Frame):
    """Simple tkinter frame to send commands and requests with arguments"""

    # noinspection PyShadowingNames
    def __init__(self, master=None, queue_send=None):
        super().__init__(master)
        self.queue_send = queue_send
        self.master = master
        self.pack()

        self.combo_device = tkk.Combobox(self, state="readonly")
        self.combo_device["values"] = list(supported_devices)
        self.combo_device.bind("<<ComboboxSelected>>", self.combo_selected)
        self.combo_device.grid(row=1, column=0)

        self.combo_command = tkk.Combobox(self, state="disabled")
        self.combo_command.bind("<<ComboboxSelected>>", self.combo_selected_command)
        self.combo_command.grid(row=1, column=1)

        self.description_text = scrolledtext.ScrolledText(self, width=44, height=4)
        self.description_text.grid(row=2, column=0, columnspan=2)

        self.button_request = tk.Button(
            self,
            text="Request",
            state="disabled",
            width=20,
            fg="green",
            command=self.send_request,
        )
        self.button_request.grid(row=3, column=0)

        self.button_command = tk.Button(
            self,
            text="Command",
            state="disabled",
            width=20,
            fg="red",
            command=self.send_command,
        )
        self.button_command.grid(row=3, column=1)

        self.selected_device = None
        self.selected_command = None
        self.dynamic_elements = dict()

        self.logger = logging.getLogger("App")
        self.logger.debug("App initialized.")

    def send_command(self):
        args = self.collect_args()
        self.logger.info(f"Command: {self.selected_command} {args}")
        self.send_command_item(
            CommandSendItem(
                self.selected_device.device_name,
                self.selected_command.name,
                arguments=args,
                request=False,
            )
        )

    def send_request(self):
        args = self.collect_args()
        if format_arg_count(self.selected_command.request_composition) == 0:
            args = ()
        self.logger.info(f"Request: {self.selected_command} {args}")
        self.send_command_item(
            CommandSendItem(
                self.selected_device.device_name,
                self.selected_command.name,
                arguments=args,
                request=True,
            )
        )

    def send_command_item(self, ci):
        self.queue_send.put(ci)

    def combo_selected(self, event):
        selected_device_name = event.widget.get()
        self.logger.info(f"Device '{selected_device_name}' selected.")
        self.selected_device = supported_devices.get(selected_device_name)
        self.combo_command["values"] = list(self.selected_device.dict_command_template)
        self.combo_command["state"] = "readonly"
        self.combo_command.set("")
        self.combo_command.update()
        self.button_request["state"] = "disabled"
        self.button_command["state"] = "disabled"
        self.clear_args()

    def combo_selected_command(self, event):
        selected_command_name = event.widget.get()
        self.logger.info(
            f"Command '{selected_command_name}' "
            f"of device '{self.selected_device.name}' selected."
        )
        self.selected_command = self.selected_device.dict_command_template.get(
            selected_command_name
        )
        self.description_text.delete(1.0, tk.END)
        if self.selected_command.description:
            self.description_text.insert(tk.INSERT, self.selected_command.description)
        self.button_request["state"] = "disabled"
        self.button_command["state"] = "disabled"
        if self.selected_command.request_composition:
            self.button_request["state"] = "active"
        if self.selected_command.command_composition:
            self.button_command["state"] = "active"
        self.button_request.update()
        self.button_command.update()
        self.create_args()

    def clear_args(self):
        for lab, widg in self.dynamic_elements.values():
            lab.destroy()
            widg.destroy()
        self.dynamic_elements = dict()

    def create_args(self):
        self.clear_args()
        row = 4

        if not self.selected_command.argument_mappings:
            return

        for key, mapping in self.selected_command.argument_mappings.items():
            lab = tk.Label(self)
            if isinstance(mapping, str):
                lab["text"] = f"{key} ({mapping})"
                widg = tk.Text(self, width=20, height=1)
            else:  # dict or list
                lab["text"] = key
                widg = tkk.Combobox(self, width=20)
                if isinstance(mapping, dict):
                    widg["values"] = list(mapping)
                else:
                    widg["values"] = mapping
            lab.grid(row=row, column=0)
            widg.grid(row=row, column=1)
            self.dynamic_elements[key] = (lab, widg)
            row += 1

    def collect_args(self):
        args = list()
        try:
            for key, (_, widg) in self.dynamic_elements.items():
                command = self.selected_command
                mapping = command.argument_mappings.get(key)

                if isinstance(mapping, str):
                    arg = command.cast_argument_as_type(key, widg.get("1.0", tk.END))
                else:
                    if isinstance(mapping, dict):
                        arg = mapping.get(widg.get())
                    else:
                        arg = command.cast_argument_as_type(key, widg.get())
                args.append(arg)
            return tuple(args)
        except ValueError:
            return None


if __name__ == "__main__":

    MULTIPROCESSING = True

    class MyHandler(logging.Handler):
        """
        A simple handler for logging events. It runs in the listener process and
        dispatches events to loggers based on the name in the received record,
        which then get dispatched, by the logging system, to the handlers
        configured for those loggers.
        """

        # noinspection PyShadowingNames
        def handle(self, record):
            logger = logging.getLogger(record.name)
            logger.handle(record)

    FORMAT = (
        "%(asctime)s %(processName)-12s %(threadName)-21s %(levelname)-8s %(message)s"
    )

    logging.basicConfig(format=FORMAT)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # logger.addHandler(logging.StreamHandler(sys.stdout))

    logger.info("Logger Started")

    device = {
        "Behringer X32": ("192.168.178.22", 10023),
        "Atlona AT-OME-SW32": ("192.168.178.202", 23),
        "Denon DN-500BD": ("192.168.178.201", 9030),
    }

    if MULTIPROCESSING:
        q = multiprocessing.Queue()

        config_queue_logger = {
            "version": 1,
            "disable_existing_loggers": True,
            "handlers": {
                "queue": {"class": "logging.handlers.QueueHandler", "queue": q},
            },
            "root": {"level": "DEBUG", "handlers": ["queue"]},
        }

        listener = logging.handlers.QueueListener(q, MyHandler())
        listener.start()

        logger.info("Queue Listener Started")

        queue_send = multiprocessing.Queue()
        queue_receive = multiprocessing.Queue()

        stop_event = multiprocessing.Event()
        thread = ProcessCmd(
            queue_receive,
            queue_send,
            device,
            stop_event,
            logger_config=config_queue_logger,
        )

    else:

        queue_send = queue.Queue()
        queue_receive = queue.Queue()

        stop_event = threading.Event()
        thread = ThreadCmd(queue_receive, queue_send, device, stop_event)

    thread.start()

    logger.info("Device Thread/Process Started")

    root = tk.Tk()
    app = Application(master=root, queue_send=queue_send)

    logger.info("App Started")
    root.mainloop()
    logger.info("App Closed")

    stop_event.set()
    logger.info("end of main")

    sys.exit(0)
