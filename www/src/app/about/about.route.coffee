class State extends Config
    constructor: ($stateProvider) ->
        
        # Name of the state
        name = 'about'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'About'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/about'
            data: cfg

        $stateProvider.state(state)