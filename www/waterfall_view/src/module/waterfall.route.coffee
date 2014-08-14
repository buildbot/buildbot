# Register new state
class State extends Config
    constructor: ($stateProvider, glMenuServiceProvider) ->

        # Name of the state
        name = 'waterfall'

        # Configuration
        glMenuServiceProvider.addGroup
            name: name
            caption: 'Waterfall View'
            icon: 'bar-chart-o'
            order: 5
        cfg =
            group: name
            caption: 'Waterfall View'

        # Register new state
        state =
            controller: "#{name}Controller"
            controllerAs: "w"
            templateUrl: "waterfall_view/views/#{name}.html"
            name: name
            url: "/#{name}"
            data: cfg

        $stateProvider.state(state)