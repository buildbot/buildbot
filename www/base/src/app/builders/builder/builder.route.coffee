class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'builder'

        # Configuration
        cfg =
            tabid: 'builders'
            pageTitle: _.template("Buildbot: builder <%= builder %>")

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder?numbuilds'
            data: cfg

        $stateProvider.state(state)
