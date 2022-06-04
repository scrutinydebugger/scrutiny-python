class UI {
    constructor(container) {
        var config = {
            content: []
        };
        this.container = container;
        this.widget_layout = new GoldenLayout(config, container);

        this.indicator_lights = {
            'red': 'assets/img/indicator-red.png',
            'yellow': 'assets/img/indicator-yellow.png',
            'green': 'assets/img/indicator-green.png',
            'grey': 'assets/img/indicator-grey.png',
        }

    }

    init() {
        this.widget_layout.init()
        var that = this
        $(window).resize(function() {
            that.resize()
        });
        this.resize();
    }

    resize() {
        var golden_layout_margin = 2
        var sidemenu = $('#sidemenu');
        var menubar_height = $('#menubar').outerHeight();
        var statusbar_height = $('#statusbar').outerHeight();
        var sidemenu_width = sidemenu.outerWidth();
        var sidemenu_height = $(window).height() - menubar_height - statusbar_height;

        var golden_layout_width = $(window).width() - sidemenu_width - golden_layout_margin;
        $('#sidemenu').outerHeight(sidemenu_height)
        $('#sidemenu').css('top', menubar_height);
        $("#menubar_corner_filler").outerWidth(sidemenu_width)
        this.container.outerWidth(golden_layout_width - 2 * golden_layout_margin);
        this.container.outerHeight(sidemenu_height - 2 * golden_layout_margin);
        this.container.css('top', menubar_height + golden_layout_margin);
        this.container.css('left', sidemenu_width + golden_layout_margin);
        this.widget_layout.updateSize(this.container.width(), this.container.height());
    }

    register_widget(widget_class, server_conn) {
        // Add component to GoldenLayout
        this.widget_layout.registerComponent(widget_class.name(),
            function(container, state) {
                widget_class.initialize(container, server_conn);
            });

        // Add menu item for drag and drop
        var div = $('<div></div>');
        div.addClass('widget_draggable_item')

        var img = $('<img/>');
        img.attr('src', widget_class.icon_path());
        img.attr('width', '64px');
        img.attr('height', '48px');

        var label = $('<span></span>')
        label.addClass('widget_draggable_label')
        label.text(widget_class.display_name())

        div.append(img);
        div.append(label);

        $('#sidemenu').append(div);
        $('#sidemenu').append($('<div class="horizontal_separator"></div>'));

        var newItemConfig = {
            title: widget_class.display_name(),
            type: 'component',
            componentName: widget_class.name(),
            componentState: {}
        };

        this.widget_layout.createDragSource(div, newItemConfig);
    }


    set_server_status(status) {
        if (status == ServerStatus.Disconnected) {
            $('#server_status_label').text('Disconnected');
            $('#server_status .indicator').attr('src', this.indicator_lights['red'])
        } else if (status == ServerStatus.Connecting) {
            $('#server_status_label').text('Connecting');
            $('#server_status .indicator').attr('src', this.indicator_lights['yellow'])
        } else if (status == ServerStatus.Connected) {
            $('#server_status_label').text('Connected');
            $('#server_status .indicator').attr('src', this.indicator_lights['green'])
        } else {
            $('#server_status_label').text('Unknown');
            $('#server_status .indicator').attr('src', this.indicator_lights['grey'])
        }
    }


    set_device_status(status) {
        if (status == DeviceStatus.Disconnected) {
            $('#device_status_label').text('Disconnected');
            $('#device_status .indicator').attr('src', this.indicator_lights['red'])
        } else if (status == DeviceStatus.Connecting) {
            $('#device_status_label').text('Connecting');
            $('#device_status .indicator').attr('src', this.indicator_lights['yellow'])
        } else if (status == DeviceStatus.Connected) {
            $('#device_status_label').text('Connected');
            $('#device_status .indicator').attr('src', this.indicator_lights['green'])
        } else {
            $('#device_status_label').text('N/A');
            $('#device_status .indicator').attr('src', this.indicator_lights['grey'])
        }
    }

    set_loaded_sfd_str(str) {
        $('#loaded_firmware_label').text(str);
    }

    set_loaded_firmware(name, version, firmware_id) {

    }
}