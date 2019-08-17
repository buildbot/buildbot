class BuildersState {
    constructor($stateProvider, glMenuServiceProvider, bbSettingsServiceProvider) {

        // Name of the state
        const name = 'builders';

        // Menu configuration
        glMenuServiceProvider.addGroup({
            name: "builds",
            caption: 'Builds',
            icon: 'cogs',
            order: 10
        });

        // Configuration
        const cfg = {
            group: "builds",
            caption: 'Builders'
        };

        // Register new state
        const state = {
            controller: `${name}Controller`,
            template: require('./builders.tpl.jade'),
            name,
            url: '/builders?tags',
            data: cfg,
            reloadOnSearch: false
        };

        $stateProvider.state(state);

        bbSettingsServiceProvider.addSettingsGroup({
            name:'Builders',
            caption: 'Builders page related settings',
            items:[{
                type:'bool',
                name:'show_old_builders',
                caption:'Show old builders',
                default_value: false
            }
            , {
                type:'bool',
                name:'show_workers_name',
                caption:'Show workers name',
                default_value: false
            }
            , {
                type:'integer',
                name:'buildFetchLimit',
                caption:'Maximum number of builds to fetch',
                default_value: 200
            }
            , {
                type:'integer',
                name:'page_size',
                caption:'Number of builders to show per page',
                default_value: 100
            }
            ]});
    }
}


angular.module('app')
.config(['$stateProvider', 'glMenuServiceProvider', 'bbSettingsServiceProvider', BuildersState]);
