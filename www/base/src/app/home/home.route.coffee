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

        bbSettingsServiceProvider.addSettingsGroup
            name:'Home'
            caption: 'Home page related settings'
            items:[
                type:'integer'
                name:'max_recent_builds'
                caption:'Max recent builds'
                default_value: 10
            ,
                type:'integer'
                name:'max_recent_builders'
                caption:'Max recent builders'
                default_value: 10
            ]
