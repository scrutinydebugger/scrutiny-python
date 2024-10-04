from scrutiny import sdk
from test.gui.base_gui_test import ScrutinyBaseGuiTest, EventType
from scrutiny.gui.watchable_index import WatchableIndex


DUMMY_DATASET_RPV = {
    '/rpv/rpvx1000' : sdk.WatchableConfiguration(server_id='rpv_111', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpvx1001' : sdk.WatchableConfiguration(server_id='rpv_222', watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DATASET_ALIAS = {
    '/alias/alias1' : sdk.WatchableConfiguration(server_id='alias_111', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias2' : sdk.WatchableConfiguration(server_id='alias_222', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias3' : sdk.WatchableConfiguration(server_id='alias_333', watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None)
}

DUMMY_DATASET_VAR = {
    '/var/var1' : sdk.WatchableConfiguration(server_id='var_111', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var2' : sdk.WatchableConfiguration(server_id='var_222', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var3' : sdk.WatchableConfiguration(server_id='var_333', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var4' : sdk.WatchableConfiguration(server_id='var_444', watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None)
}


All_DUMMY_DATA = {
    sdk.WatchableType.Variable: DUMMY_DATASET_VAR,
    sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS,
    sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV,
}

class TestWatchableIndex(ScrutinyBaseGuiTest):
    def setUp(self) -> None:
        super().setUp()
        self.index = WatchableIndex()

        self.index.signals.cleared.connect(lambda : self.declare_event(EventType.WATCHABLE_INDEX_CLEARED))
        self.index.signals.changed.connect(lambda : self.declare_event(EventType.WATCHABLE_INDEX_CHANGED))
        self.index.signals.filled.connect(lambda : self.declare_event(EventType.WATCHABLE_INDEX_READY))
    
    def test_events(self):
        self.index.clear()
        self.assert_events([])   # No events
    
        self.index.set_content({sdk.WatchableType.Variable: DUMMY_DATASET_VAR})
        self.assert_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED]) 
        self.index.set_content({sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS})
        self.assert_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED]) 
        self.index.set_content({sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV})
        self.assert_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED, EventType.WATCHABLE_INDEX_READY]) 

        self.index.set_content({sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV})
        self.assert_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED, EventType.WATCHABLE_INDEX_READY]) 

        self.index.clear_content_by_types([sdk.WatchableType.Variable])
        self.assert_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED]) 
        self.index.clear_content_by_types([sdk.WatchableType.Alias])
        self.assert_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED]) 
        self.index.clear_content_by_types([sdk.WatchableType.RuntimePublishedValue])
        self.assert_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED, EventType.WATCHABLE_INDEX_CLEARED]) 


        self.index.set_content({
            sdk.WatchableType.Variable: DUMMY_DATASET_VAR,
            sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS,
            sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV
        })

        self.assert_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED, EventType.WATCHABLE_INDEX_READY]) 

        self.index.clear_content_by_types([sdk.WatchableType.Variable, sdk.WatchableType.Alias, sdk.WatchableType.RuntimePublishedValue])
        self.assert_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED, EventType.WATCHABLE_INDEX_CLEARED]) 

        self.index.set_content({
            sdk.WatchableType.Variable: DUMMY_DATASET_VAR,
            sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS,
            sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV
        })
        self.assert_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED, EventType.WATCHABLE_INDEX_READY]) 

        self.index.clear()
        self.assert_events_and_clear([EventType.WATCHABLE_INDEX_CHANGED, EventType.WATCHABLE_INDEX_CLEARED]) 

    def test_ignore_empty_data(self):
        self.index.set_content({
            sdk.WatchableType.Alias : DUMMY_DATASET_ALIAS,
            sdk.WatchableType.RuntimePublishedValue : {}  # Should be ignored
        })

        self.assertTrue(self.index.has_data(sdk.WatchableType.Alias))
        self.assertFalse(self.index.has_data(sdk.WatchableType.RuntimePublishedValue))
        self.assertFalse(self.index.has_data(sdk.WatchableType.Variable))
    
    def test_get(self):
        self.index.set_content(All_DUMMY_DATA)


    def tearDown(self):
        super().tearDown()
