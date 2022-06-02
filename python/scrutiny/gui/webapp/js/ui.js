class UI {
    constructor(container) {
        var config = {
            content: []
        };
        this.container = container;
        this.widget_layout = new GoldenLayout(config, container);

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

    register_widget(widget_class) {
        // Add component to GoldenLayout
        this.widget_layout.registerComponent(widget_class.name(),
            function(container, state) {
                widget_class.initialize(container, state);
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
        // element.text(widget_class.display_name())
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
}