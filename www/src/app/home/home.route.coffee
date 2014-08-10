class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'home'

        # Configuration
        cfg =
            caption: 'Home'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/'
            data: cfg