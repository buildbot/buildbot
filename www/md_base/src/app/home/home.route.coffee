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
                default_value: false
            ,
                type: 'hidden'
                name: 'panels'
                default_value: [
                    name: 'overview'
                    title: 'overview'
                    collapsed: false
                    template: 'views/overview_panel.html'
                ,
                    name: 'current_builds'
                    title: 'current builds'
                    collapsed: true
                    template: 'views/current_builds_panel.html'
                ,
                    name: 'recent_builds'
                    title: 'recent builds'
                    collapsed: true
                    template: 'views/recent_builds_panel.html'
                ]
            ]
