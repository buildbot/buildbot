class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'builds.changes'

        # Register new state
        $stateProvider.state
            controller: "changesController"
            controllerAs: 'changes'
            templateUrl: "views/#{name}.html"
            name: name
            url: "/changes"
            data:
                title: 'Builds / Latest Changes'
