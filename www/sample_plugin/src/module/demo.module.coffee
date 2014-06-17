name = 'buildbot.sample'
dependencies = [
    'ui.router'
    'buildbot.common'
]

# Register new module
m = angular.module name, dependencies
angular.module('app').requires.push(name)

m.config ['$stateProvider',
    ($stateProvider) ->

        # Name of the state
        name = 'demo'

        # Configuration
        cfg =
            tabid: name
            tabhash: "##{name}"
            caption: 'Demo'

        # Register new state
        state =
            templateUrl: "sample_plugin/views/#{name}.html"
            name: name
            url: '/demo'
            data: cfg

        $stateProvider.state(state)
]

m.controller 'demoController',
  ['$log', '$scope', 'buildbotService', "sample_plugin_config"
      ($log, $scope, buildbotService, config) ->
          $scope.config = config
  ]
