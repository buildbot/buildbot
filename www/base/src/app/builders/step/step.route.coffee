class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'step'

        # Configuration
        cfg =
            tabid: 'builders'
            pageTitle: _.template("Buildbot: build <%= build %> step: <%= step %>")

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder/builds/:build/steps/:step'
            data: cfg
