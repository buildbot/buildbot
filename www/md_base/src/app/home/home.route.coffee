class State extends Config
    constructor: ($stateProvider, menuServiceProvider, bbSettingsServiceProvider) ->

        # Name of the state
        name = 'home'

        menuServiceProvider.addItem
            name: name
            caption: 'Home'
            icon: 'home'
            order: 0

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            controllerAs: name
            templateUrl: "views/#{name}.html"
            name: name
            url: '/'

        bbSettingsServiceProvider.addSettingsGroup
            name: 'home'
            caption: 'Home'
            description: 'Settings to customize the display of Home page'
            items: [
                type: 'bool'
                name: 'lock_panels'
                caption: 'Lock panels'
                default_value: true
            ,
                type: 'hidden'
                name: 'panels'
                default_value: [
                    name: 'overview'
                    title: 'overview'
                    collapsed: false
                ,
                    name: 'current_builds'
                    title: 'current builds'
                    collapsed: true
                ,
                    name: 'recent_builds'
                    title: 'recent builds'
                    collapsed: true
                ]
            ]
