class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'builds.masters'

        # Register new state
        $stateProvider.state
            controller: "mastersController"
            controllerAs: 'masters'
            templateUrl: "views/#{name}.html"
            name: name
            url: "/builds/masters/"
            data:
                title: 'Builds / Masters'
