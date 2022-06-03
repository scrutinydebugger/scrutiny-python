class ServerConnection {


    constructor(ui, hostname = '127.0.0.1', port = 8765) {
        this.update_ui_interval = 500;
        this.reconnect_interval = 500;

        this.ui = ui
        this.set_endpoint(hostname, port)
        this.socket = null
        this.server_status = ServerStatus.Disconnected
        this.device_status = DeviceStatus.NA
        this.callback_dict = {}
        this.enable_reconnect = true

        this.update_ui()
    }

    set_endpoint(hostname, port) {
        this.hostname = hostname
        this.port = port
    }

    start() {
        var that = this
        this.enable_reconnect = true
        this.create_socket()
        this.server_status = ServerStatus.Connecting

        setInterval(function() {
            that.update_ui();
        }, this.update_ui_interval)

        this.update_ui();
    }

    stop() {
        this.enable_reconnect = false
        if (this.socket !== null) {
            this.socket.close()
        }
    }

    create_socket() {
        var that = this; // Javascript is such a beautiful language
        this.socket = new WebSocket("ws://" + this.hostname + ":" + this.port);
        this.socket.onmessage = function(e) {
            that.on_socket_message_callback(e.data)
        }
        this.socket.onclose = function(e) {
            that.on_socket_close_callback(e);
        }
        this.socket.onopen = function(e) {
            that.on_socket_open_callback(e);
        }
        this.socket.on_error = function(e) {
            that.on_socket_error_callback(e);
        }
    }

    update_ui() {
        this.ui.set_server_status(this.server_status)
        this.ui.set_device_status(this.device_status)
    }

    on_socket_close_callback(e) {
        this.server_status = ServerStatus.Disconnected
        this.device_status = DeviceStatus.NA
        this.update_ui();
        if (this.enable_reconnect) {
            this.try_reconnect(this.reconnect_interval)
        }
    }

    on_socket_open_callback(e) {
        this.server_status = ServerStatus.Connected
        this.device_status = DeviceStatus.NA
        this.update_ui();
    }

    on_socket_error_callback(e) {
        this.server_status = ServerStatus.Disconnected
        this.device_status = DeviceStatus.NA
        this.update_ui();
        if (this.enable_reconnect) {
            this.try_reconnect(this.reconnect_interval)
        }
    }

    try_reconnect(timeout) {
        var that = this
        setTimeout(function() {
            that.create_socket()
        }, timeout)
    }

    // When we receive a datagram from the server
    on_socket_message_callback(msg) {
        try {
            obj = JSON.parse(msg)

            // Server is angry. Try to understand why
            if (obj.cmd == "error") {

                error_message = 'Got an error response from the server for request "' + obj.request_cmd + '".'
                if (obj.hasOwnProperty('msg')) {
                    error_message += obj.msg
                }

                console.log(error_message)
            } else { // Server is happy, spread the news
                if (this.callback_dict.hasOwnProperty(obj.cmd)) {
                    for (let i = 0; i < this.callback_dict[obj.cmd].length; i++) {
                        this.callback_dict[obj.cmd][i](obj);
                    }
                }
            }
        } catch (error) {
            // Server is drunk. Ignore him.
            console.log('Error while processing message from server. ' + error)
        }
    }

    register_callback(cmd, callback) {
        if (!this.callback_dict.hasOwnProperty(cmd)) {
            this.callback_dict[cmd] = []
        }

        this.callback_dict[cmd].push(callback)
    }
}