class ChangeBuildsState {
    constructor($stateProvider, bbSettingsServiceProvider) {
        // Name of the state
        const name = 'changebuilds';

        // Configuration
        const cfg = {}

        // Register new state
        const state = {
            controller: `${name}Controller`,
            template: require('./changebuilds.tpl.jade'),
            name,
            url: '/changes/:changeid',
            data: cfg,
            reloadOnSearch: false
        }

        $stateProvider.state(state);

        bbSettingsServiceProvider.addSettingsGroup({
            name:'ChangeBuilds',
            caption: 'ChangeBuilds page related settings',
            items:[{
                type:'integer',
                name:'buildsFetchLimit',
                caption:'Maximum number of builds to fetch for the selected change',
                default_value: ''
            }]
        });
    }
}

angular.module('app')
.config(['$stateProvider', 'bbSettingsServiceProvider', ChangeBuildsState]);
