class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'masters'

        # Menu configuration
        cfg =
            group: "builds"
            caption: 'Build Masters'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/masters'
            data: cfg

        $stateProvider.state(state)
