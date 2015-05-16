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
                name: 'overview_collapsed'
                caption: 'Collapse overview panel'
                default_value: false
            ,
                type: 'bool'
                name: 'current_builds_collapsed'
                caption: 'Collapse current builds panel'
                default_value: true
            ,
                type: 'bool'
                name: 'recent_builds_collapsed'
                caption: 'Collapse recent builds panel'
                default_value: true
            ]
