class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'builds.builder'

        # Register new state
        $stateProvider.state
            controller: "builderController"
            controllerAs: 'builder'
            templateUrl: "views/#{name}.html"
            name: name
            url: "/builds/builder/:builder_id/"
            data:
                title: 'Builds / Builder'
