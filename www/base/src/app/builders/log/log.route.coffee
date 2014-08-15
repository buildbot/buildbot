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
            url: '/builders/:builder/build/:build/step/:step/log/:log'
            data: cfg

        $stateProvider.state(state)