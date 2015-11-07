class State extends Config
    constructor: (menuServiceProvider, bbSettingsServiceProvider, $stateProvider) ->

        # Name of the state
        name = 'settings'

        menuServiceProvider.addItem
            name: name
            caption: 'Settings'
            icon: 'toggle'
            order: 20

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            controllerAs: name
            templateUrl: "views/#{name}.html"
            name: name
            url: "/#{name}"
            data:
                title: 'Settings'
                classname: 'settings'
