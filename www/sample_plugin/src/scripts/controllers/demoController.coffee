angular.module('app').controller 'demoController',
['$log', '$scope', 'buildbotService', "sample_plugin_config"
    ($log, $scope, buildbotService, config) ->
        $scope.config = config
]
