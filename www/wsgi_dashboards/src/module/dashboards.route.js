/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
// Register new state
class WsgiDashboardsState {
    constructor($stateProvider, glMenuServiceProvider, config) {
        for (let dashboard of Array.from(config.plugins.wsgi_dashboards)) {
            // Name of the state
            const { name } = dashboard;
            let { caption } = dashboard;
            if (caption == null) { caption = _.capitalize(name); }
            if (dashboard.order == null) { dashboard.order = 5; }
            // Configuration
            glMenuServiceProvider.addGroup({
                name,
                caption,
                icon: dashboard.icon,
                order: dashboard.order
            });
            const cfg = {
                group: name,
                caption
            };

            // Register new state
            const state = {
                controller: "wsgiDashboardsController",
                templateUrl: `wsgi_dashboards/${name}/index.html`,
                name,
                url: `/${name}`,
                data: cfg
            };
            $stateProvider.state(state);
        }
    }
}

class WsgiDashboardsController {
    constructor($scope, $state) {}
}


angular.module('wsgi_dashboards')
.config(['$stateProvider', 'glMenuServiceProvider', 'config', WsgiDashboardsState])
.controller('wsgiDashboardsController', ['$scope', '$state', WsgiDashboardsController]);
