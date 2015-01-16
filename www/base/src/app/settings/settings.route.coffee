class Settings extends Config
    constructor: ($stateProvider, glMenuServiceProvider) ->

        # Name of the state
        name = 'settings'

        # Menu configuration
        glMenuServiceProvider.addGroup
            name: name
            caption: 'Settings'
            icon: 'sliders'
            order: 99

        # Configuration
        cfg =
            group: name
            caption: 'Settings'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/settings'
            data: cfg

        $stateProvider.state(state)