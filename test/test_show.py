import unittest
import os
import shutil

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from viewcontrol import show

class TestShow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.project_folder = os.path.abspath("testing")
        if os.path.exists(cls.project_folder):
            shutil.rmtree(cls.project_folder)
        cls.session = show.create_session(cls.project_folder)
        show.MediaElement.set_project_path(cls.project_folder)
        cls.mm = None

    @classmethod
    def tearDownClass(cls):
        #shutil.rmtree(cls.project_folder)
        return

    def setUp(self):
        return

    def tearDown(self):
        print(self._testMethodName)
        return

    def test_0100_media_element_manager(self):
        TestShow.mm = show.MediaElementManager(TestShow.session)

    def test_0101_still_element_jpg(self):
        still_jpg = show.StillElement("poster", "media/Big_buck_bunny_poster_big.jpg")
        TestShow.mm.add_element(still_jpg)

    def test_0102_still_element_png(self):
        still_png = show.StillElement("screen", "media/Big_Buck_Bunny_1080p_Opening_Screen.png")
        TestShow.mm.add_element(still_png)

    def test_0103_still_element_png(self):
        TestShow.sele = show.StartElement()
        #wird nicht zu liste hinzugefügt

    def test_0104_video_element_mp4(self):
        video_avi = show.VideoElement("bbb", "media/Big_Buck_Bunny_1080p_clip.mp4")
        TestShow.mm.add_element(video_avi)

    def test_0200_logic_element_manager(self):
        TestShow.llist = show.LogicElementManager(TestShow.session)

    def test_0201_loop_element(self):
        TestShow.llist.add_element_loop(3)

    def test_0300_show(self):
        TestShow.show = show.Show('testing', TestShow.session)

    def test_0301_show_add_elements(self):
        TestShow.show.add_module(TestShow.mm.get_element_with_name("poster"))
        TestShow.show.add_module(TestShow.llist.get_element_with_name("LoopStart_1"))
        TestShow.show.add_module(TestShow.mm.get_element_with_name("screen"))
        TestShow.show.add_module(TestShow.mm.get_element_with_name("bbb"))
        TestShow.show.add_module(TestShow.llist.get_element_with_name("LoopEnd_1"))

    def test_0302_add_jumptotarget(self):
        TestShow.show.add_jumptotarget("start trailer")
        self.assertTrue(True)

    def test_0303_show_add_element_with_command_list(self):
        command = show.Command("test1", "CommandDenon", "Pause")
        TestShow.show.add_module(TestShow.mm.get_element_with_name("poster"), commands=command)

    def test_0304_show_add_command_to_element(self):
        command = show.Command("test2", "CommandDenon", "Play")
        TestShow.show.sequence[0].add_command(command)
        TestShow.show.save_show()

    def test_0305_video_element_avi(self):
        video_avi = show.VideoElement("bbb_end", "media/Big_Buck_Bunny_1080p_clip2.avi")
        TestShow.show.add_module(video_avi)

    def test_0305_show_change_position(self):
        #TestShow.show.change_position(TestShow.show.sequence[3], 1)
        #need funtion to get element of position
        return

    def test_0400_load_show_from_db(self):
        TestShow.playlist = show.Show("testing", TestShow.session)
        TestShow.playlist.load_show()

    def test_0500_playlist_next(self):
        #test of loop defineds in 0301 and 0201
        i = 0
        while i<20:
            TestShow.playlist.next()
            i = i + 1


if __name__ == '__main__':
    unittest.main()

