class State extends Config
    constructor: ($stateProvider) ->

        # Name of the state
        name = 'buildrequest'

        # Register new state
        state =
            controller: "#{name}Controller"
            templateUrl: "views/#{name}.html"
            name: name
            data: {}
            url: '/buildrequests/:buildrequest?redirect_to_build'

        $stateProvider.state(state)
