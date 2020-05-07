import os
import shutil
import sys
import time
import unittest
import queue
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from viewcontrol import show
from viewcontrol.remotecontrol import processcmd, threadcommunicationbase
from viewcontrol.remotecontrol.threadcommunicationbase import ComType

# if True add a empty file instead of media elememnts
# WARNING! dont forget run propper test_case before testing the module
skip_workload = False


class TestDevices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project_folder = os.path.expanduser("testing")
        cls.show = show.Show(cls.project_folder)
        cls.show.show_load("testing_devices")
        for dev in cls.show.show_options.devices.values():
            dev.enabled = True
        logging.basicConfig(level=logging.INFO)
        cls.logger = logging.getLogger("TestDevices")
        cls.cmd_status_queue = queue.Queue()
        cls.cmd_controll_queue = queue.Queue()
        cls.process_cmd = processcmd.ThreadCmd(
            cls.logger,
            cls.cmd_status_queue,
            cls.cmd_controll_queue,
            cls.show.show_options.devices,
        )
        cls.process_cmd.start()
        time.sleep(2)

    @classmethod
    def tearDownClass(cls):
        # shutil.rmtree(cls.project_folder)
        print("\n##### Terminate with ctr+C #####\n\n")
        return

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_AtlonaATOMESW32(self):
        cmd_1 = show.CommandObject("Lock", "AtlonaATOMESW32", "Lock")
        cmd_2 = show.CommandObject("InputStatus", "AtlonaATOMESW32", "InputStatus")
        cmd_3 = show.CommandObject("Status", "AtlonaATOMESW32", "Status")
        cmd_4 = show.CommandObject("Set Output", "AtlonaATOMESW32", "Set Output", 1, 1)
        cmd_5 = show.CommandObject("PWSTA", "AtlonaATOMESW32", "PWSTA")
        cmd_6 = show.CommandObject("Set Output", "AtlonaATOMESW32", "Set Output", 2, 1)
        cmd_7 = show.CommandObject("Unlock", "AtlonaATOMESW32", "Unlock")
        cmd_8 = show.CommandObject(
            "Set Output Fail", "AtlonaATOMESW32", "Set Output", 1, 3
        )
        self.assertEqual(
            self.send_and_wait_for_answer(cmd_1).type, ComType.command_success
        )
        self.assertEqual(
            self.send_and_wait_for_answer(cmd_2).type, ComType.request_success
        )
        self.assertEqual(
            self.send_and_wait_for_answer(cmd_3).type, ComType.request_success
        )
        self.assertEqual(
            self.send_and_wait_for_answer(cmd_4).type, ComType.command_success
        )
        self.assertEqual(
            self.send_and_wait_for_answer(cmd_5).type, ComType.request_success
        )
        time.sleep(2)
        self.assertEqual(
            self.send_and_wait_for_answer(cmd_6).type, ComType.command_success
        )
        self.assertEqual(
            self.send_and_wait_for_answer(cmd_7).type, ComType.command_success
        )
        input(
            "\n##### press enter, then change channel on any output (10 sec timeout!)#####\n\n"
        )
        b, answ = self.wait_for_status("AVx1", 10)
        self.assertTrue(b)
        self.assertEqual(answ.type, ComType.message_status)
        self.assertEqual(
            self.send_and_wait_for_answer(cmd_8).type, ComType.command_failed
        )

    def test_DenonDN500BD(self):
        # if is aktive run test else skip
        cmd_1 = show.CommandObject("status", "DenonDN500BD", "Status")
        cmd_2 = show.CommandObject("pause", "DenonDN500BD", "Pause")
        cmd_3 = show.CommandObject("play", "DenonDN500BD", "Play")
        cmd_4 = show.CommandObject(
            "jump to start chapter", "DenonDN500BD", "Track Jump", 1
        )
        cmd_5 = show.CommandObject("get time", "DenonDN500BD", "Elapse Time")
        input(
            "\n###### Remove Disk And Close Tray, Go to Home Screen (HOME-Button), press Enter to continue #####\n\n"
        )
        anw_1 = self.send_and_wait_for_answer(cmd_1)
        self.assertIsNotNone(anw_1)
        self.assertEqual(anw_1.type, ComType.request_success)
        self.assertIn("STDVHM", anw_1.recv_answer_string)
        input(
            "\n###### Open tray and insert disk, press Enter and close tray  (10 sec timeout!) #####\n\n"
        )
        self.assertTrue(self.wait_for_status("@0CDTC", 10))
        self.assertTrue(self.wait_for_status("@0CDCI"))
        b, obj = self.wait_for_status("@0STPL", 10)
        self.assertTrue(b)
        self.assertEqual(obj.type, ComType.message_status)
        input(
            "\n###### navigate to movie and play the second chapter, then press Enter #####\n\n"
        )
        anw_2 = self.send_and_wait_for_answer(cmd_2)
        self.assertEqual(anw_2.type, ComType.command_success)
        time.sleep(0.5)
        anw_3 = self.send_and_wait_for_answer(cmd_3)
        self.assertEqual(anw_3.type, ComType.command_success)
        anw_4 = self.send_and_wait_for_answer(cmd_4)
        self.assertTrue(self.wait_for_status, "@0Tr0001")
        self.assertEqual(anw_4.type, ComType.command_success)
        time.sleep(2)
        anw_5 = self.send_and_wait_for_answer(cmd_5)
        self.assertEqual(anw_5.type, ComType.request_success)
        # TODO get total track number and jump to next track

    def send_and_wait_for_answer(self, cmd, timeout=5):
        TestDevices.cmd_controll_queue.put((cmd, 0))
        try:
            while True:
                answ = TestDevices.cmd_status_queue.get(timeout=timeout)
                if answ.command_obj == cmd:
                    return answ
        except:
            return "timeout reached"

    def wait_for_status(self, status_string, timeout=5):
        try:
            while True:
                answ = TestDevices.cmd_status_queue.get(timeout=timeout)
                if status_string in answ.recv_answer_string:
                    return True, answ
        except:
            return False, "timeout reached"


if __name__ == "__main__":
    unittest.main()
