class WorkersState {
    constructor($stateProvider, bbSettingsServiceProvider) {

        // Name of the state
        const name = 'workers';

        // Menu Configuration
        const cfg = {
            group: "builds",
            caption: 'Workers'
        };

        // Register new state
        $stateProvider.state({
            controller: `${name}Controller`,
            template: require('./workers.tpl.jade'),
            name,
            url: '/workers?numbuilds',
            data: cfg
        });

        // worker page is actually same as worker, just filtered
        $stateProvider.state({
            controller: `${name}Controller`,
            template: require('./workers.tpl.jade'),
            name: 'worker',
            url: '/workers/:worker?numbuilds',
            data: {}});

        bbSettingsServiceProvider.addSettingsGroup({
            name:'Workers',
            caption: 'Workers page related settings',
            items:[{
                type:'bool',
                name:'show_old_workers',
                caption:'Show old workers',
                default_value: false
            }
            , {
                type:'bool',
                name:'showWorkerBuilders',
                caption:'Show list of builders for each worker (can take a lot of time)',
                default_value: false
            }
            ]});
    }
}


angular.module('app')
.config(['$stateProvider', 'bbSettingsServiceProvider', WorkersState]);
