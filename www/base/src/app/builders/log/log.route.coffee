class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'log'

        # Configuration
        cfg =
            tabid: 'builders'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder/builds/:build/steps/:step/logs/:log'
            data: cfg

        $stateProvider.state(state)
