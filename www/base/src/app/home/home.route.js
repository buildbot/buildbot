class HomeState {
    constructor($stateProvider, glMenuServiceProvider, bbSettingsServiceProvider) {

        // Name of the state
        const name = 'home';

        // Menu configuration
        glMenuServiceProvider.addGroup({
            name,
            caption: 'Home',
            icon: 'home',
            order: 1
        });

        const cfg = {
            group: name,
            caption: 'Home'
        };

        // Register new state
        $stateProvider.state({
            controller: `${name}Controller`,
            template: require('./home.tpl.jade'),
            name,
            url: '/',
            data: cfg
        });

        bbSettingsServiceProvider.addSettingsGroup({
            name:'Home',
            caption: 'Home page related settings',
            items:[{
                type:'integer',
                name:'max_recent_builds',
                caption:'Max recent builds',
                default_value: 10
            }
            , {
                type:'integer',
                name:'max_recent_builders',
                caption:'Max recent builders',
                default_value: 10
            }
            ]});
    }
}


angular.module('app')
.config(['$stateProvider', 'glMenuServiceProvider', 'bbSettingsServiceProvider', HomeState]);
