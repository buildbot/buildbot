class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'builds.schedulers'

        # Register new state
        $stateProvider.state
            controller: "schedulersController"
            controllerAs: "schedulers"
            templateUrl: "views/#{name}.html"
            name: name
            url: "/schedulers"
            data:
                title: 'Builds / Schedulers'
