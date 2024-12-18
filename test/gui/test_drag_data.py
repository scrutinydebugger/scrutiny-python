#    test_drag_data.py
#        A test suite to test the tools that revolves around drag & drop
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

from test import ScrutinyUnitTest
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData, SingleWatchableDescriptor, WatchableListDescriptor
from PySide6.QtCore import QMimeData, QByteArray
import json

class NonSerializableObject:
    pass

class TestDragData(ScrutinyUnitTest):
    def test_drag_data(self):

        with self.assertRaises(TypeError):
            ScrutinyDragData(type='asd', data_copy=None, data_move=None)

        
        self.assertIsNone(ScrutinyDragData(ScrutinyDragData.DataType.WatchableFullTree, data_copy=NonSerializableObject()).to_mime())
        
        self.assertIsInstance(ScrutinyDragData(ScrutinyDragData.DataType.WatchableFullTree, data_copy={}).to_mime(), QMimeData)
        
        mime_data = QMimeData()
        self.assertIsNone(ScrutinyDragData.from_mime(mime_data))

        mime_data.setData('application/json', b'\x00')
        self.assertIsNone(ScrutinyDragData.from_mime(mime_data))

        data = {}
        mime_data.setData('application/json', QByteArray.fromStdString(json.dumps(data)))
        self.assertIsNone(ScrutinyDragData.from_mime(mime_data))

        data = {'type' : ScrutinyDragData.DataType.WatchableFullTree.value}
        mime_data.setData('application/json', QByteArray.fromStdString(json.dumps(data)))
        self.assertIsNone(ScrutinyDragData.from_mime(mime_data))

        data = {'type' : ScrutinyDragData.DataType.WatchableFullTree.value, 'data_copy':None, 'data_move':None}
        mime_data.setData('application/json', QByteArray.fromStdString(json.dumps(data)))
        self.assertIsNotNone(ScrutinyDragData.from_mime(mime_data))

    def test_serializable_watchable_elements(self):
        desc = SingleWatchableDescriptor(fqn='a/b/c', text='hello')
        d = desc.to_serializable()
        self.assertIsInstance(d, dict)
        self.assertEqual(d['fqn'], desc.fqn)
        self.assertEqual(d['text'], desc.text)

        desc2 = SingleWatchableDescriptor.from_serializable(d)
        self.assertEqual(desc2, desc)
        self.assertIsNot(desc2, desc)
        

        self.assertIsNone(SingleWatchableDescriptor.from_serializable(None))
        self.assertIsNone(SingleWatchableDescriptor.from_serializable({}))
        self.assertIsNone(SingleWatchableDescriptor.from_serializable({'text':'hello'}))
        self.assertIsNone(SingleWatchableDescriptor.from_serializable({'fqn':'hello'}))
        self.assertIsNone(SingleWatchableDescriptor.from_serializable({'text':123, 'fqn':'hello'}))
        self.assertIsNone(SingleWatchableDescriptor.from_serializable({'text':'hello', 'fqn':123}))
        
        self.assertIsNotNone(SingleWatchableDescriptor.from_serializable({'text':'hello', 'fqn':"/a/b/c"}))


        desc3 = WatchableListDescriptor(
            data = [
                SingleWatchableDescriptor(text='aaa', fqn='xxx'),
                SingleWatchableDescriptor(text='bbb', fqn='yyy'),
                SingleWatchableDescriptor(text='ccc', fqn='zzz'),
            ]
        )

        desc4 = WatchableListDescriptor.from_mime(desc3.to_mime())

        self.assertEqual(desc4, desc3)

        self.assertIsNone(WatchableListDescriptor.from_serializable(None))
        self.assertIsNone(WatchableListDescriptor.from_serializable({}))
        self.assertIsNone(WatchableListDescriptor.from_serializable([None, None]))
        self.assertIsNone(WatchableListDescriptor.from_serializable([{}, {}]))
        self.assertIsNotNone(WatchableListDescriptor.from_serializable([{'text':'hello', 'fqn':"/a/b/c"}, {'text':'hello2', 'fqn':"/a/b/c2"}]))


        self.assertIsNone(WatchableListDescriptor.from_drag_data(None))
        self.assertIsNone(WatchableListDescriptor.from_drag_data(ScrutinyDragData(type=ScrutinyDragData.DataType.WatchableFullTree)))
        self.assertIsNone(WatchableListDescriptor.from_drag_data(ScrutinyDragData(type=ScrutinyDragData.DataType.WatchableList)))
        self.assertIsNotNone(WatchableListDescriptor.from_drag_data(ScrutinyDragData(type=ScrutinyDragData.DataType.WatchableList, data_copy=[])))

        self.assertIsNone(WatchableListDescriptor.from_mime(None))
        self.assertIsNone(WatchableListDescriptor.from_mime(QMimeData()))
