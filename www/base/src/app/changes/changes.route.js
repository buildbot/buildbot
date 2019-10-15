class ChangesState {
    constructor($stateProvider, bbSettingsServiceProvider) {

        // Name of the state
        const name = 'changes';

        // Configuration
        const cfg = {
            group: "builds",
            caption: 'Last Changes'
        };

        // Register new state
        const state = {
            controller: `${name}Controller`,
            template: require('./changes.tpl.jade'),
            name,
            url: '/changes?id',
            data: cfg,
            reloadOnSearch: false
        };

        $stateProvider.state(state);

        bbSettingsServiceProvider.addSettingsGroup({
            name:'Changes',
            caption: 'Changes page related settings',
            items:[{
                type:'integer',
                name:'changesFetchLimit',
                caption:'Maximum number of changes to fetch',
                default_value: 50
            }]});
    }
}


angular.module('app')
.config(['$stateProvider', 'bbSettingsServiceProvider', ChangesState]);
