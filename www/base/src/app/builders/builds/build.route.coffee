class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'build'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders/:builder/builds/:build'
            data:
                pageTitle: _.template("Buildbot: builder <%= builder %> build <%= build %>")

        $stateProvider.state(state)
