class State extends Config
    constructor: ($stateProvider, glMenuServiceProvider) ->

        # Name of the state
        name = 'about'

        # Menu configuration
        glMenuServiceProvider.addGroup
            name: name
            caption: 'About'
            icon: 'info-circle'
            order: 99

        # Configuration
        cfg =
            group: name
            caption: 'About'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/about'
            data: cfg

        $stateProvider.state(state)
