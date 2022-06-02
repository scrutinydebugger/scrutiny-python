class VarListWidget {
    //static name = 'watch';
    //static display_name = 'Watch Window';
    static initialize(container, sate) {
        container.getElement().html('<h2 style="text-align:center">VarList!</h2>');
    }

    static name() {
        return 'varlist';
    }
    static display_name() {
        return 'Variable List';
    }

    static icon_path() {
        return 'assets/img/treelist-96x128.png';
    }
}