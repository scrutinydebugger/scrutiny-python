var scrutiny_client_config = {
    'server': {
        'hostname': '127.0.0.1',
        'port': 8765
    }
}

function load_config() {
    if (typeof config_from_python !== 'undefined') {
        scrutiny_client_config = config_from_python
    }
}

(function() {
    load_config()

    ui = new UI($('#layout-container'));
    ui.init()
    let config = scrutiny_client_config
    server_conn = new ServerConnection(ui)
    server_conn.start(config['server']['hostname'], config['server']['port'])

    ui.register_widget(VarListWidget, server_conn)
    ui.register_widget(WatchWidget, server_conn)

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