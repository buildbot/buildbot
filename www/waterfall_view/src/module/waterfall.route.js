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
            templateUrl: `waterfall_view/views/${name}.html`,
            name,
            url: `/${name}`,
            data: cfg
        };

        $stateProvider.state(state);
    }
}

angular.module('waterfall_view')
.config(['$stateProvider', 'glMenuServiceProvider', WaterfallState]);
