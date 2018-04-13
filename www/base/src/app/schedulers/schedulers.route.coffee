class State
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'schedulers'

        # Configuration
        cfg =
            group: "builds"
            caption: 'Schedulers'

        # Register new state
        $stateProvider.state
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            url: '/schedulers'
            data: cfg


angular.module('app')
.config(['$stateProvider', State])