class State extends Config
    constructor: ($stateProvider, glMenuServiceProvider, bbSettingsServiceProvider) ->

        # Name of the state
        name = 'home'

        # Menu configuration
        glMenuServiceProvider.addGroup
            name: name
            caption: 'Home'
            icon: 'home'
            order: 1

        cfg =
            group: name
            caption: 'Home'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/'
            data: cfg
