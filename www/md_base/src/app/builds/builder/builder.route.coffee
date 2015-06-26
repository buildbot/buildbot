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
            url: "/builder/:builderid"
            data:
                title: 'Builder'
