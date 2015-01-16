class State extends Config
    constructor: ($stateProvider, glMenuServiceProvider, bbSettingsServiceProvider) ->

        # Name of the state
        name = 'builders'

        # Menu configuration
        glMenuServiceProvider.addGroup
            name: "builds"
            caption: 'Builds'
            icon: 'cogs'
            order: 10

        # Configuration
        cfg =
            group: "builds"
            caption: 'Builders'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/builders'
            data: cfg

        $stateProvider.state(state)
