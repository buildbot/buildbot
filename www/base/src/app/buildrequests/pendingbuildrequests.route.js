class PendingBuildRequestsState {
    constructor($stateProvider, bbSettingsServiceProvider) {

        // Name of the state
        const name = 'pendingbuildrequests';

        // Configuration
        const cfg = {
            group: "builds",
            caption: 'Pending Buildrequests'
        };

        // Register new state
        const state = {
            controller: `${name}Controller`,
            template: require('./pendingbuildrequests.tpl.jade'),
            name,
            url: '/pendingbuildrequests',
            data: cfg
        };

        $stateProvider.state(state);

        bbSettingsServiceProvider.addSettingsGroup({
            name:'BuildRequests',
            caption: 'Buildrequests page related settings',
            items:[{
                type:'integer',
                name:'buildrequestFetchLimit',
                caption:'Maximum number of pending buildrequests to fetch',
                default_value: 50
            }
            ]});
    }
}


angular.module('app')
.config(['$stateProvider', 'bbSettingsServiceProvider', PendingBuildRequestsState]);
