class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'about'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: "/#{name}"
