


from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.core.user_messages_manager import UserMessagesManager
from scrutiny.tools.typing import *
from dataclasses import dataclass
import time

class TestUserMessagesManager(ScrutinyBaseGuiTest):
    @dataclass
    class MessageShow:
        t:float
        msg:str

    @dataclass
    class MessageClear:
        t:float


    def setUp(self):
        self.msg_clear_list:List[TestUserMessagesManager.MessageClear] = []
        self.msg_shown_list:List[TestUserMessagesManager.MessageShow] = []
        def show_callbacks(msg:str) -> None:
            self.msg_shown_list.append(self.MessageShow(t=time.perf_counter(), msg=msg))

        def clear_callback() -> None:
             self.msg_clear_list.append(self.MessageClear(t=time.perf_counter()))

        self.manager = UserMessagesManager()
        self.manager.signals.show_message.connect(show_callbacks)
        self.manager.signals.clear_message.connect(clear_callback)

        return super().setUp()

    def test_messages_are_queued(self):
        tstart = time.perf_counter()
        self.manager.register_message("aaa", "hello1", 1.0)
        self.manager.register_message("bbb", "hello2", 2.0)
        self.manager.register_message("ccc", "hello3", 3.0)

        self.wait_equal_with_events(lambda: len(self.msg_clear_list), 3, timeout=5)

        self.assertEqual( len(self.msg_shown_list), 3)
        self.assertEqual( len(self.msg_clear_list), 3)

        self.assertEqual(self.msg_shown_list[0].msg, "hello1")
        self.assertEqual(self.msg_shown_list[1].msg, "hello2")
        self.assertEqual(self.msg_shown_list[2].msg, "hello3")

        def assertWithin(val, target, margin):
            self.assertLessEqual(val, target+margin)
            self.assertGreaterEqual(val, target-margin)
        
        MARGIN = 0.3

        assertWithin(self.msg_shown_list[0].t - tstart, 0, MARGIN)
        assertWithin(self.msg_shown_list[1].t - tstart, 1, MARGIN)
        assertWithin(self.msg_shown_list[2].t - tstart, 2, MARGIN)

        assertWithin(self.msg_clear_list[0].t - tstart, 1, MARGIN)
        assertWithin(self.msg_clear_list[1].t - tstart, 2, MARGIN)
        assertWithin(self.msg_clear_list[2].t - tstart, 3, MARGIN)  

        assertWithin(self.msg_clear_list[0].t - self.msg_shown_list[0].t, 1, MARGIN)
        assertWithin(self.msg_clear_list[1].t - self.msg_shown_list[1].t, 1, MARGIN)
        assertWithin(self.msg_clear_list[2].t - self.msg_shown_list[2].t, 1, MARGIN)


    def test_expired_messages_doesnt_show(self):
        self.manager.register_message("aaa", "msg1", 1.0)
        self.manager.register_message("bbb", "msg2", 0.5)   # Will be expired
        self.manager.register_message("ccc", "msg3", 0.2)   # Will be expired
        self.manager.register_message("ddd", "msg4", 2.0)


        self.wait_equal_with_events(lambda: len(self.msg_clear_list), 2, timeout=4)
        for i in range(5):
            time.sleep(0.01)
            self.process_events()
        
        self.assertEqual(len(self.msg_clear_list), 2)
        self.assertEqual(len(self.msg_shown_list), 2)

        self.assertEqual(self.msg_shown_list[0].msg, 'msg1')
        self.assertEqual(self.msg_shown_list[1].msg, 'msg4')

    def test_same_id_override_previous_cancel_if_first(self):
        self.manager.register_message("aaa", "msg1", 1)
        self.manager.register_message("aaa", "msg2", 1)

        self.wait_equal_with_events(lambda: len(self.msg_clear_list), 2, timeout=3)
        for i in range(5):
            time.sleep(0.01)
            self.process_events()
        
        self.assertEqual(len(self.msg_clear_list), 2)
        self.assertEqual(len(self.msg_shown_list), 2)

        self.assertEqual(self.msg_shown_list[0].msg, 'msg1')
        self.assertEqual(self.msg_shown_list[1].msg, 'msg2')
        
        self.assertLess(self.msg_clear_list[0].t - self.msg_shown_list[0].t, 0.4)
        

    def test_same_id_override_previous(self):
        self.manager.register_message("aaa", "msg1", 1)
        self.manager.register_message("bbb", "msg2", 2) # Will never show
        self.manager.register_message("bbb", "msg3", 2)

        self.wait_equal_with_events(lambda: len(self.msg_clear_list), 2, timeout=4)

        self.assertEqual(len(self.msg_clear_list), 2)
        self.assertEqual(len(self.msg_shown_list), 2)

        self.assertEqual(self.msg_shown_list[0].msg, 'msg1')
        self.assertEqual(self.msg_shown_list[1].msg, 'msg3')
        
