class State extends Config
    constructor: (menuServiceProvider, $stateProvider) ->

        # Name of the state
        name = 'about'

        menuServiceProvider.addItem
            name: name
            caption: 'About'
            icon: 'info'
            order: 30

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            controllerAs: name
            templateUrl: "views/#{name}.html"
            name: name
            url: "/#{name}"
            data:
                title: 'About'
                classname: 'about'
