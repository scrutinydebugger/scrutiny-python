class WatchWidget {
    //static name = 'watch';
    //static display_name = 'Watch Window';
    static initialize(container, sate) {
        container.getElement().html('<h2>Watch!</h2>');
    }

    static name() {
        return 'watch';
    }
    static display_name() {
        return 'Watch Window';
    }
}