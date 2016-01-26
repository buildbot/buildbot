class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'builds.workers'

        # Register new state
        $stateProvider.state
            controller: "workersController"
            controllerAs: 'workers'
            templateUrl: "views/#{name}.html"
            name: name
            url: "/workers"
            data:
                title: 'Builds / Workers'
