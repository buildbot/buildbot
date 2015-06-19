class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'builds.schedulers'

        # Register new state
        $stateProvider.state
            controller: "schedulersController"
            controllerAs: name
            templateUrl: "views/#{name}.html"
            name: name
            url: "/builds/schedulers/"
            data:
                title: 'Builds / Schedulers'
