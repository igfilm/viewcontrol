import pytest

# TODO remove this event type from test
from pynput.keyboard import Key

import viewcontrol
from viewcontrol.remotecontrol.threadcommunicationbase import ComType


@pytest.fixture(scope="function")
def show(project_folder) -> viewcontrol.Show:
    return viewcontrol.Show(project_folder)


@pytest.fixture(scope="function")
def show_t(show):
    show.show_load("testing")
    return show


class TestShow:
    def test_1000_show(self, show):
        assert len(show.show_list) == 0
        show.show_new("testA")
        # still 0 because no element was created
        assert len(show.show_list) == 0
        show.module_add_text("test1", "test1", 1)
        assert len(show.show_list) == 1
        assert show.show_list[0] == "testA"

    def test_1001_show(self, show):
        assert show.show_list[0] == "testA"
        assert not show.show_new("testA")
        assert not show.show_load("testB")
        assert show.show_new("testB")
        show.module_add_text("test2", "test2", 2)
        assert len(show.show_list) == 2
        assert show.show_close()

    def test_1002_show(self, show):
        assert show.show_delete("testA")
        assert len(show.show_list) == 1
        assert not show.show_load("testA")
        assert show.show_list[0] == "testB"
        assert show.show_name is None
        assert not show.show_delete()
        assert show.show_load("testB")
        assert show.show_delete()
        assert len(show.show_list) == 0

    def test_1003_show(self, show):
        assert len(show.show_list) == 0
        assert not show.show_new("testA")
        assert len(show.show_list) == 0
        assert not show.show_new("testB")
        assert len(show.show_list) == 0
        assert show.show_new("testC")
        show.module_add_text("test3", "test3", 3)
        assert len(show.show_list) == 1
        assert not show.show_load(None)

    def test_1004_show_copy(self, show):
        assert len(show.show_list) == 1
        assert show.show_copy("testC", "testC_copy")
        assert len(show.show_list) == 2
        assert show.show_load("testC_copy")
        assert show.count == 1
        assert show._module_get_at_pos(0)._media_element_id == 3


def scr_media(data_folder, name) -> str:
    return str(data_folder.joinpath("media", name))


def test_set_skip_workload():
    viewcontrol.show.MediaElement._skip_high_workload_functions = True


class TestShowPlaylist:
    def test_1000_show(self, project_folder, show_t):
        # is show database created
        assert project_folder.joinpath("vcproject.db3").exists()
        assert show_t.count == 0

    def test_1101_append_pdf_big(self, project_folder, show_t, source_data):
        assert show_t.count == 0
        show_t.show_new("testing")
        # add pdf, check if files are created
        show_t.module_add_still("poster", scr_media(source_data, "bbb_poster.pdf"), 8)
        assert project_folder.joinpath("bbb_poster_w.jpg").exists()
        assert project_folder.joinpath("bbb_poster_c.jpg").exists()
        assert show_t.count == 1

    def test_1102_append_same(self, project_folder, show_t, source_data):
        assert show_t.count == 1
        # add same (source-)file(name) twice , check if counter is added on files
        show_t.module_add_still(
            "anouncement", scr_media(source_data, "bbb_title_anouncement.jpg"), 2
        )
        show_t.module_add_still(
            "anouncement_copy", scr_media(source_data, "bbb_title_anouncement.jpg"), 3
        )
        assert project_folder.joinpath("bbb_title_anouncement_c.jpg").exists()
        assert project_folder.joinpath("bbb_title_anouncement_c_2.jpg").exists()
        assert project_folder.joinpath("bbb_title_anouncement_w.jpg").exists()
        assert project_folder.joinpath("bbb_title_anouncement_w_2.jpg").exists()
        assert show_t.count == 3

    def test_1203_delete_same(self, show_t):
        assert show_t.count == 3
        show_t.module_remove(2)
        assert show_t.count == 2
        # assert self.media_elements)
        # check if obj is still in MEdiaElements

    def test_1213_append_identical_name(self, show_t, source_data):
        assert show_t.count == 2
        # try to add same name twice. result should be a two behind name of
        # second sequence module.
        assert show_t.module_add_still(
            "bbb_picture", scr_media(source_data, "bbb_poster_bunny_big.jpg"), 5
        )

        assert show_t.module_add_still(
            "bbb_picture", scr_media(source_data, "bbb_poster_rodents_big.jpg"), 5
        )
        bbb1 = show_t._module_get_with_name("bbb_picture")
        assert bbb1 is not None
        assert bbb1.media_element._file_path_c == "bbb_poster_bunny_big_c.jpg"
        bbb2 = show_t._module_get_with_name("bbb_picture_2")
        assert bbb2 is not None
        assert bbb2.media_element._file_path_c == "bbb_poster_rodents_big_c.jpg"

        assert show_t.count == 4

    def test_1214_rename_media(self, show_t):
        assert show_t.count == 4
        assert show_t.module_rename(3, "bbb_picture_bunny")
        assert show_t._module_get_with_name("bbb_picture_bunny") is not None

    def test_1304_append_loop(self, show_t):
        assert show_t._module_get_with_name("bbb_picture_bunny") is not None
        # add loop and change its position in playlist (this procedure shall be used in GUI to)
        assert show_t.module_add_loop(3, pos=3)
        assert show_t._module_get_with_name("#LoopStart_1").position == 3
        assert show_t._module_get_with_name("#LoopEnd_1").position == 4
        assert show_t.module_move_up(3)
        assert show_t._module_get_with_name("#LoopStart_1").position == 2
        assert show_t._module_get_with_name("#LoopEnd_1").position == 4
        assert show_t.module_move_down(4)
        assert show_t._module_get_with_name("#LoopStart_1").position == 2
        assert show_t._module_get_with_name("#LoopEnd_1").position == 5

    def test_1305_append_jumpto(self, show_t):
        assert show_t.count == 6
        assert show_t.module_add_jumptotarget(
            "skip loop",
            "event_key_end",
            commands_delay_tuple=(
                viewcontrol.show.CommandObject(
                    "dimm light", "CommandDmx", "Group10-Intesity"
                ),
                30,
            ),
        )

        assert show_t._module_get_at_pos(6).name == "#skip loop"
        assert show_t.count == 7

    def test_1306_add_delete_another_jumpto(self, show_t):
        assert show_t.count == 7
        assert show_t.module_add_jumptotarget("#skip loop", "event_xy")
        assert show_t._module_get_at_pos(7).name == "#skip loop_2"

    def test_1307_rename_logic(self, show_t):
        assert show_t.count == 8
        assert show_t.module_rename(7, "xy fuubar")
        assert show_t._module_get_at_pos(7).name == "#xy fuubar"

    def test_1308_delete_logic(self, show_t):
        assert show_t._module_get_at_pos(7).name == "#xy fuubar"
        assert show_t.module_remove(7)
        assert show_t.count == 7

    def test_1316_append_text_element(self, project_folder, show_t):
        assert show_t.count == 7
        assert show_t.module_add_text("next", "next at viewntrol", 5)
        assert project_folder.joinpath("_next.jpg").exists()
        assert show_t.count == 8

    def test_1317_change_text(self, show_t):
        assert show_t.module_text_change_text(7, "next at viewcontrol")
        assert (
            show_t._module_get_at_pos(7).media_element.text == "next at " "viewcontrol"
        )

    def test_1320_append_video(self, project_folder, show_t, source_data):
        assert show_t.count == 8
        assert show_t.module_add_video(
            "clip2_kite", "media/Big_Buck_Bunny_1080p_clip2.avi", t_start=0.1, pos=8
        )
        assert show_t.module_add_video(
            "clip1_apple",
            scr_media(source_data, "Big_Buck_Bunny_1080p_clip.mp4"),
            pos=8,
        )
        assert project_folder.joinpath("Big_Buck_Bunny_1080p_clip2_c.mp4").exists()
        assert project_folder.joinpath("Big_Buck_Bunny_1080p_clip2_w.mp4").exists()
        assert project_folder.joinpath("Big_Buck_Bunny_1080p_clip_c.mp4").exists()
        assert project_folder.joinpath("Big_Buck_Bunny_1080p_clip_w.mp4").exists()
        assert show_t._module_get_with_name("clip2_kite").position == 9
        assert show_t._module_get_with_name("clip1_apple").position == 8
        assert show_t.count == 10

    def test_1401_add_command(self, show_t):
        assert show_t.count == 10
        commands = [
            (
                viewcontrol.show.CommandObject(
                    "jump to start chapter", "DenonDN500BD", "Track Jump", 1
                ),
                0,
            ),
            (
                viewcontrol.show.CommandObject(
                    "swich video to BluRay", "AtlonaATOMESW32", "Set Output", 2, 1
                ),
                0,
            ),
        ]
        assert show_t.module_add_text(
            "film ab", "FILM AB", 1, commands_delay_tuple=commands
        )

        assert show_t.count == 11
        assert len(show_t._module_get_at_pos(10).list_commands) == 2
        command2 = (
            viewcontrol.show.CommandObject(
                "swich video to PC", "AtlonaATOMESW32", "Set Output", 3, 1
            ),
            1,
        )
        assert show_t.module_add_command_to_pos(0, command2)
        assert len(show_t._module_get_at_pos(0).list_commands) == 1

    def test_1402_add_event(self, show_t):
        em1 = viewcontrol.show.KeyEventModule(Key.end, "on_press", name="exit loop")
        em1.jump_to_target_element = show_t.list_jump_to_target[0]
        assert show_t.event_module_add(em1)
        assert len(show_t.list_event) == 1
        assert show_t.list_event[0] == em1
        em2 = viewcontrol.show.ComEventModule(
            "DenonDN500BD",
            ComType.message_status,
            "Status",
            ["Pause"],
            name="EOM (End of Movie)",
        )
        cmd5 = viewcontrol.show.CommandObject("play disk", "DenonDN500BD", "Play", None)
        em2.command_add((cmd5, 2))
        assert show_t.event_module_add(em2)
        assert len(show_t.eventlist) == 2
        assert len(show_t.list_event) == 2
        assert show_t.list_event[1] == em2

    def test_1402_rename_copy_event(self, show_t):
        assert len(show_t.eventlist) == 2
        assert show_t.event_module_copy(show_t.eventlist[1], "fuubar") is not None

        assert len(show_t.eventlist) == 3
        assert show_t.eventlist[2].name == "fuubar"
        assert not show_t.eventlist[1] == show_t.eventlist[2]
        assert show_t.eventlist[1]._device == "DenonDN500BD"
        assert show_t.eventlist[2]._device == "DenonDN500BD"
        assert len(show_t.eventlist[1].list_commands) == len(
            show_t.eventlist[2].list_commands
        )

        assert show_t.event_module_copy(show_t.eventlist[0], "fuubar2") is not None

        assert len(show_t.eventlist) == 4
        assert (
            show_t.eventlist[0].jump_to_target_element
            == show_t.eventlist[3].jump_to_target_element
        )
        assert show_t.event_module_delete(show_t.eventlist[2])
        assert show_t.event_module_delete(show_t.eventlist[2])
        assert len(show_t.eventlist) == 2

    def test_1500_copy_module(self, show_t):
        assert len(show_t.eventlist) == 2
        assert len(show_t._module_get_at_pos(0).list_commands) == 1
        assert show_t.module_copy(10)
        assert not show_t._module_get_at_pos(10) == show_t._module_get_at_pos(11)

        assert show_t.count == 12
        assert len(show_t._module_get_at_pos(11).list_commands) == 2

    def test_2001_copy_show(self, show_t):
        assert len(show_t._module_get_at_pos(11).list_commands) == 2
        assert show_t.show_copy(None, "testing_copy")
        assert show_t.show_load("testing_copy")
        assert show_t.count == 12
        assert len(show_t.eventlist) == 2
        assert len(show_t._module_get_at_pos(11).list_commands) == 2
        assert "testing" in show_t.show_list

    def test_2001_rename_show(self, show):
        assert show.show_load("testing_copy")
        assert show.show_rename("testing_copy_renamed")
        assert show.count == 12
        assert show.show_list == [
            "testC",
            "testC_copy",
            "testing",
            "testing_copy_renamed",
        ]

    def test_2003_rename_show_back(self, show_t):
        assert show_t.show_list == [
            "testC",
            "testC_copy",
            "testing",
            "testing_copy_renamed",
        ]
        assert show_t.show_rename("testing_copy", old_name="testing_copy_renamed")
        assert show_t.show_list, ["testC", "testC_copy", "testing", "testing_copy"]

        assert show_t.show_load("testing_copy")
        assert show_t.count == 12

    def test_2010_change_command(self, show):
        pass

    def test_2011_add_by_id(self, show_t):
        assert show_t.module_add_media_by_id(4, 10)
        assert show_t.count == 13
        assert (
            show_t._module_get_at_pos(12).media_element.id
            == show_t._module_get_at_pos(0).media_element.id
        )

        assert show_t.module_add_command_by_id_to_pos(12, 4, delay=-9999)
        assert len(show_t.playlist[12].list_commands) == 1
        assert (
            show_t.playlist[12].list_commands[0][0].id
            == show_t.playlist[0].list_commands[0][0].id
        )

        assert show_t.playlist[12].list_commands[0][1] > 0
        assert show_t.playlist[0].list_commands[0][1] == 1
        assert show_t.module_remove_all_commands_from_pos(12)
        assert len(show_t.playlist[12].list_commands) == 0

    def test_2011_check_remove_command(self, show_t):
        assert len(show_t.playlist[12].list_commands) == 0


class TestShowOptions:

    con_denon = ("192.168.178.201", 9030)
    con_atlona = ("192.168.178.202", 23)

    def test_1000(self, show):
        assert len(show.show_options.devices) > 0
        assert "AtlonaATOMESW32" in show.show_options.devices.keys()
        assert "DenonDN500BD" in show.show_options.devices.keys()
        assert show.show_options.set_device_property(
            show.show_options.devices.get("DenonDN500BD"),
            enabled=True,
            connection=TestShowOptions.con_denon,
        )

        assert (
            TestShowOptions.con_denon
            == show.show_options.devices.get("DenonDN500BD").connection
        )

    def test_1001(self, show):
        assert (
            TestShowOptions.con_denon
            == show.show_options.devices.get("DenonDN500BD").connection
        )

        assert show.show_options.devices.get("DenonDN500BD").enabled
        assert not show.show_options.devices.get("AtlonaATOMESW32").enabled
        assert show.show_options.set_device_property(
            show.show_options.devices.get("AtlonaATOMESW32"),
            enabled=True,
            connection=TestShowOptions.con_atlona,
        )
