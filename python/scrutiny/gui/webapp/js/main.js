(function() {
    ui = new UI($('#layout-container'));
    ui.init()

    ui.register_widget(VarListWidget)
    ui.register_widget(WatchWidget)
})();

/*
var socket = new WebSocket("ws://127.0.0.1:8765");

socket.onmessage = function(event) {
    console.log(`[message] Data received from server: ${event.data}`);
};

socket.onopen = function() {
    socket.send('{"cmd": "echo", "payload": "patate"}')
};
*/