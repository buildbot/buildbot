// Register new state
class WaterfallState {
    constructor($stateProvider, glMenuServiceProvider) {

        // Name of the state
        const name = 'waterfall';

        // Configuration
        glMenuServiceProvider.addGroup({
            name,
            caption: 'Waterfall View',
            icon: 'bar-chart-o',
            order: 5
        });
        const cfg = {
            group: name,
            caption: 'Waterfall View'
        };

        // Register new state
        const state = {
            controller: `${name}Controller`,
            controllerAs: "w",
            template: require('./waterfall.tpl.jade'),
            name,
            url: `/${name}?tags`,
            data: cfg,
            reloadOnSearch: false
        };

        $stateProvider.state(state);
    }
}

angular.module('waterfall_view')
.config(['$stateProvider', 'glMenuServiceProvider', WaterfallState])
.config(['$locationProvider', function($locationProvider) {
    $locationProvider.hashPrefix('');
}])
.run([
    '$rootScope',
    '$location',
    function($rootScope, $location) {
      $rootScope.location = $location
    }
])