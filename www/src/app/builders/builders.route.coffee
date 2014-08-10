class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'builders'

        # Configuration
        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Builders'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders'
            data: cfg

        $stateProvider.state(state)