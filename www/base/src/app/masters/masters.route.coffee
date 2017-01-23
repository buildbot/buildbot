class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'masters'

        # Menu configuration
        cfg =
            group: "builds"
            caption: 'Build Masters'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/masters'
            data: cfg

        # master page is actually same as masters, just filtered
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: 'master'
            url: '/masters/:master'
            data: {}
