class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'log'

        # Configuration
        cfg =
            tabid: 'builders'
            pageTitle: _.template("Buildbot: log: <%= log %>")

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder/builds/:build/steps/:step/logs/:log?jump_to_line'
            data: cfg

        $stateProvider.state(state)
