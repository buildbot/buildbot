angular.module('app').config ['$stateProvider', 'topMenuStatesProvider'
    (topMenuStatesProvider, $stateProvider) ->
        plugin =
            name: 'sample_plugin'

        routes =
            demo:
                caption: "Demo"
                url: "/demo"

        for id, cfg of routes
            cfg.tabid ?= id
            cfg.tabhash = "##{id}"
            state =
                controller: cfg.controller ? "#{id}Controller"
                templateUrl: cfg.templateUrl ? "#{plugin.name}/views/#{id}.html"
                name: id
                url: cfg.url
                data: cfg

        topMenuStatesProvider.state(state)
        $stateProvider.state(state)
]