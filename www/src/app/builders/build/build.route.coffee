class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'build'

        # Configuration
        cfg =
            tabid: 'builders'
            tabhash: "##{name}"

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder/build/:build'
            data: cfg

        $stateProvider.state(state)