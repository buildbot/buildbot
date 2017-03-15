# Register new state
class State extends Config
    constructor: ($stateProvider, glMenuServiceProvider, config) ->
        for dashboard in config.plugins.wsgi_dashboards
            # Name of the state
            name = dashboard.name
            caption = dashboard.caption
            caption ?= _.capitalize(name)
            dashboard.order ?= 5
            # Configuration
            glMenuServiceProvider.addGroup
                name: name
                caption: caption
                icon: dashboard.icon
                order: dashboard.order
            cfg =
                group: name
                caption: caption

            # Register new state
            state =
                controller: "wsgiDashboardsController"
                templateUrl: "wsgi_dashboards/#{name}/index.html"
                name: name
                url: "/#{name}"
                data: cfg
            $stateProvider.state(state)

class WsgiDashboards extends Controller
    constructor: ($scope, $state) ->
