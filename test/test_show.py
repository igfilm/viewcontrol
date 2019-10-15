import unittest
import os
import shutil
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from viewcontrol import show

class TestShow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.project_folder = os.path.expanduser("testing")
        if os.path.exists(cls.project_folder):
            shutil.rmtree(cls.project_folder)

    @classmethod
    def tearDownClass(cls):
        #shutil.rmtree(cls.project_folder)
        return

    def setUp(self):
        self.show = show.Show('testing', TestShow.project_folder)
        print('')
        self.t_start = time.time()

    def tearDown(self):
        print("{} - {} s".format(self._testMethodName, time.time()-self.t_start), sep="")

    def test_1000_show(self):
        #is show database created
        self.assertTrue(os.path.exists(self.project_folder+'/vcproject.db3'))
        self.assertEqual(self.show.count, 0)

    def test_1101_append_pdf_big(self):
        self.assertEqual(self.show.count, 0)
        #add pdf, check if files are created        
        self.show.add_module_still("poster", "media/bbb_poster.pdf", 8)
        self.assertTrue(os.path.exists(self.project_folder+'/bbb_poster_w.jpg'))
        self.assertTrue(os.path.exists(self.project_folder+'/bbb_poster_c.jpg'))
        self.assertEqual(self.show.count, 1)

    def test_1102_append_same(self):
        self.assertEqual(self.show.count, 1)
        #add same (source-)file(name) twice , check if counter is added on files
        self.show.add_module_still("anouncement", "media/bbb_title_anouncement.jpg", 2)
        self.show.add_module_still("anouncement_copy", "media/bbb_title_anouncement.jpg", 3)
        self.assertTrue(os.path.exists(self.project_folder+'/bbb_title_anouncement_c.jpg'))
        self.assertTrue(os.path.exists(self.project_folder+'/bbb_title_anouncement_c_2.jpg'))
        self.assertTrue(os.path.exists(self.project_folder+'/bbb_title_anouncement_w.jpg'))
        self.assertTrue(os.path.exists(self.project_folder+'/bbb_title_anouncement_w_2.jpg'))
        self.assertEqual(self.show.count, 3)

    def test_1203_delete_same(self):
        self.assertEqual(self.show.count, 3)
        self.show.remove_module(2)
        self.assertEqual(self.show.count, 2)
        #self.assertEqual(self.media_elements)
        #check if obj is still in MEdiaElements

    def test_1213_append_identical_name(self):
        self.assertEqual(self.show.count, 2)
        #try to add same name twice. result should be a two behind name of 
        #second sequence module.
        self.show.add_module_still("bbb_picture", "media/bbb_poster_bunny_big.jpg", 5)
        self.show.add_module_still("bbb_picture", "media/bbb_poster_rodents_big.jpg", 5)
        bbb1 = self.show.get_module_with_element_name("bbb_picture")
        self.assertIsNotNone(bbb1)
        self.assertEqual(bbb1.media_element.file_path_c, "bbb_poster_bunny_big_c.jpg")
        bbb2 = self.show.get_module_with_element_name("bbb_picture_2")
        self.assertIsNotNone(bbb2)
        self.assertEqual(bbb2.media_element.file_path_c, "bbb_poster_rodents_big_c.jpg")
        self.assertEqual(self.show.count, 4)

    def test_1304_append_loop(self):
        self.assertEqual(self.show.count, 4)
        #add loop and change its position in playlist (this procedure shall be used in GUI to)
        self.show.add_module_loop(3, pos=3)
        self.assertEqual(self.show.get_module_with_element_name("LoopStart_1").position, 3)
        self.assertEqual(self.show.get_module_with_element_name("LoopEnd_1").position, 4)
        self.show.move_element_up(3)
        self.assertEqual(self.show.get_module_with_element_name("LoopStart_1").position, 2)
        self.assertEqual(self.show.get_module_with_element_name("LoopEnd_1").position, 4)
        self.show.move_element_down(4)
        self.assertEqual(self.show.get_module_with_element_name("LoopStart_1").position, 2)
        self.assertEqual(self.show.get_module_with_element_name("LoopEnd_1").position, 5)

    def test_1305_append_jumpto(self):
        self.assertEqual(self.show.count, 6)
        self.show.add_module_jumptotarget("exit loop", 
            commands=show.Command(
                "dimm light", "CommandDmx", "Group10-Intesity", 30))
        self.assertEqual(self.show.count, 7)

    def test_1320_append_video(self):
        self.assertEqual(self.show.count, 7)
        self.show.add_module_video("clip2_kite", "media/Big_Buck_Bunny_1080p_clip2.avi", pos=7)
        self.show.add_module_video("clip1_apple", "media/Big_Buck_Bunny_1080p_clip.mp4", pos=7)
        self.assertTrue(os.path.exists(self.project_folder+'/Big_Buck_Bunny_1080p_clip2_c.mp4'))
        self.assertTrue(os.path.exists(self.project_folder+'/Big_Buck_Bunny_1080p_clip2_w.mp4'))
        self.assertTrue(os.path.exists(self.project_folder+'/Big_Buck_Bunny_1080p_clip_c.mp4'))
        self.assertTrue(os.path.exists(self.project_folder+'/Big_Buck_Bunny_1080p_clip_w.mp4'))
        self.assertEqual(self.show.get_module_with_element_name("clip2_kite").position, 8)
        self.assertEqual(self.show.get_module_with_element_name("clip1_apple").position, 7) 
        self.assertEqual(self.show.count, 9)

    def test_1401_add_command(self):
        commands=[
            show.Command("jump to start", "CommandDenon", "Track Jump", 1),
            show.Command("swich video to BluRay", "CommandAtlona", "Set Output", 1, 2)]
        self.show.add_command_to_pos(8, commands)
        command2 = show.Command("swich video to BluRay", "CommandAtlona", "Set Output", 1, 3)
        self.show.add_command_to_pos(0, command2)
        #add asserts for check

    #def _test_1205_append_gif(self):
    #    self.show.add_module_still("chemgif", "media/1.3-B.gif", 10)



if __name__ == '__main__':
    unittest.main(failfast=True)