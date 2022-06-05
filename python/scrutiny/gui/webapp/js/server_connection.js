class ServerConnection {


    constructor(ui, hostname = '127.0.0.1', port = 8765) {
        let that = this;
        this.update_ui_interval = 500;
        this.reconnect_interval = 500;
        this.connect_timeout = 1500;
        this.get_status_interval = 2000;

        this.ui = ui
        this.set_endpoint(hostname, port)
        this.socket = null
        this.server_status = ServerStatus.Disconnected
        this.device_status = DeviceStatus.NA
        this.loaded_sfd = null

        this.callback_dict = {}
        this.enable_reconnect = true
        this.connect_timeout_handle = null;

        this.get_status_interval_handle = null


        this.register_callback("inform_server_status", function(data) {
            that.inform_server_status_callback(data)
        })

        this.set_disconnected()
        this.update_ui()
    }

    set_disconnected() {
        this.server_status = ServerStatus.Disconnected
        this.device_status = DeviceStatus.NA
        this.loaded_sfd = null
        this.update_ui()
    }

    set_endpoint(hostname, port) {
        this.hostname = hostname
        this.port = port
    }

    start() {
        let that = this
        this.enable_reconnect = true
        this.create_socket()
        this.server_status = ServerStatus.Connecting

        setInterval(function() {
            that.update_ui();
        }, this.update_ui_interval)

        this.update_ui();
    }

    stop() {
        this.enable_reconnect = false;
        if (this.socket !== null) {
            this.socket.close()
        }
        this.set_disconnected();
    }

    send_request(cmd, params = {}) {
        if (this.socket !== null) {
            if (this.socket.readyState == this.socket.OPEN) {
                try {
                    params['cmd'] = cmd;
                    let payload = JSON.stringify(params)
                    console.debug('Sending: ' + payload)
                    this.socket.send(payload)
                } catch (e) {
                    console.error('Cannot send request with command=' + cmd + '. Error: ' + e)
                }
            }
        }
    }

    create_socket() {
        let that = this; // Javascript is such a beautiful language
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

        this.connect_timeout_handle = setTimeout(function() {
            if (that.socket != that.socket.OPEN) {
                that.socket.close()
            }
        }, this.connect_timeout)
    }

    start_get_status_periodic_call() {
        let that = this;
        this.stop_get_status_periodic_call()
        that.send_request('get_server_status')
        this.get_status_interval_handle = setInterval(function() {
            that.send_request('get_server_status')
        }, this.get_status_interval)
    }

    stop_get_status_periodic_call() {
        if (this.get_status_interval_handle !== null) {
            clearInterval(this.get_status_interval_handle)
            this.get_status_interval_handle = null
        }
    }

    update_ui() {
        this.ui.set_server_status(this.server_status)
        this.ui.set_device_status(this.device_status)
        this.ui.set_loaded_sfd(this.loaded_sfd)
    }

    clear_connect_timeout() {
        if (this.connect_timeout_handle != null) {
            clearTimeout(this.connect_timeout_handle)
            this.connect_timeout_handle = null
        }
    }

    on_socket_close_callback(e) {
        this.set_disconnected();
        this.clear_connect_timeout()
        this.stop_get_status_periodic_call()

        if (this.enable_reconnect) {
            this.try_reconnect(this.reconnect_interval)
        }
    }

    on_socket_open_callback(e) {
        this.server_status = ServerStatus.Connected
        this.device_status = DeviceStatus.NA
        this.update_ui();
        this.clear_connect_timeout()

        this.start_get_status_periodic_call()
    }

    on_socket_error_callback(e) {
        this.set_disconnected();
        this.clear_connect_timeout()
        this.stop_get_status_periodic_call()
        if (this.enable_reconnect) {
            this.try_reconnect(this.reconnect_interval)
        }
    }

    try_reconnect(delay) {
        let that = this
        setTimeout(function() {
            that.create_socket()
        }, delay)
    }

    // When we receive a datagram from the server
    on_socket_message_callback(msg) {
        try {
            console.debug('Received: ' + msg)
            let obj = JSON.parse(msg)

            // Server is angry. Try to understand why
            if (obj.cmd == "error") {

                let error_message = 'Got an error response from the server for request "' + obj.request_cmd + '".'
                if (obj.hasOwnProperty('msg')) {
                    error_message += obj.msg
                }

                console.error(error_message)
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

    // =====

    inform_server_status_callback(data) {
        let device_status_str_to_obj = {
            'unknown': DeviceStatus.NA,
            'disconnected': DeviceStatus.Disconnected,
            'connecting': DeviceStatus.Connecting,
            'connected': DeviceStatus.Connecting,
            'connected_ready': DeviceStatus.Connected
        }

        try {
            try {
                this.device_status = device_status_str_to_obj[data.device_status];
            } catch {
                this.device_status = DeviceStatus.NA;
                console.error('[inform_server_status] Received a bad device status')
            }

            try {
                this.loaded_sfd = data['loaded_sfd'];
            } catch (e) {
                this.loaded_sfd = null
                console.error('[inform_server_status] Cannot read loaded firmware. ' + e)
            }


        } catch (e) {
            console.error('[inform_server_status] Unexpected error. ' + e)
        }

        this.update_ui()
    }
}