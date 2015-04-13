class State extends Config
    constructor: (menuServiceProvider, $stateProvider) ->

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
