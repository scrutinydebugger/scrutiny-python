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
        var menubar_height = $('#menubar').height();
        var statusbar_height = $('#statusbar').height();
        var sidemenu_width = $('#sidemenu').width();
        var golden_layout_width = $(window).width() - sidemenu_width - 1;
        var golden_layout_height = $(window).height() - menubar_height - statusbar_height - 2;
        $('#sidemenu').height(golden_layout_height)
        this.container.width(golden_layout_width);
        this.container.height(golden_layout_height);
        this.container.css('top', menubar_height + 1);
        this.container.css('left', sidemenu_width + 1);
        this.widget_layout.updateSize(golden_layout_width, golden_layout_height);
    }

    register_widget(widget_class) {
        // Add component to GoldenLayout
        this.widget_layout.registerComponent(widget_class.name(),
            function(container, state) {
                widget_class.initialize(container, state);
            });

        // Add menu item for drag and drop
        var element = $('<li></li>');
        element.text(widget_class.display_name())
        element.addClass('widget_drag_icon')
        $('#widget-list').append(element);

        var newItemConfig = {
            title: widget_class.display_name(),
            type: 'component',
            componentName: widget_class.name(),
            componentState: {}
        };

        this.widget_layout.createDragSource(element, newItemConfig);
    }
}