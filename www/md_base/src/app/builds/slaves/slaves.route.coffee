class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'builds.slaves'

        # Register new state
        $stateProvider.state
            controller: "slavesController"
            controllerAs: 'slaves'
            templateUrl: "views/#{name}.html"
            name: name
            url: "/slaves"
            data:
                title: 'Builds / Slaves'
