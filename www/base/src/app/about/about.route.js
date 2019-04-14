class AboutState {
    constructor($stateProvider, glMenuServiceProvider) {

        // Name of the state
        const name = 'about';

        // Menu configuration
        glMenuServiceProvider.addGroup({
            name,
            caption: 'About',
            icon: 'info-circle',
            order: 99
        });

        // Configuration
        const cfg = {
            group: name,
            caption: 'About'
        };

        // Register new state
        const state = {
            controller: `${name}Controller`,
            templateUrl: `views/${name}.html`,
            name,
            url: '/about',
            data: cfg
        };

        $stateProvider.state(state);
    }
}


angular.module('app')
.config(['$stateProvider', 'glMenuServiceProvider', AboutState]);
