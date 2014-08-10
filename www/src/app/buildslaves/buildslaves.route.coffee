class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'buildslaves'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Build Slaves'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/buildslaves'
            data: cfg