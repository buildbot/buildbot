class State extends Config
    constructor: (menuServiceProvider, $stateProvider) ->

        # Name of the state
        name = 'builds'

        menuServiceProvider.addItem
            name: name
            caption: 'Builds'
            icon: 'gear'
            order: 10

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            controllerAs: name
            templateUrl: "views/#{name}.html"
            name: name
            url: "/#{name}"
            data:
                title: 'Builds'
                classname: 'builds'
