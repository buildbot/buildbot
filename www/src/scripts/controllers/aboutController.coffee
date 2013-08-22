angular.module('app').controller 'aboutController',
['$log', '$scope', '$location', 'bower_configs', 'config'
    ($log, $scope, $location, bower_configs, config) ->
        # translate github urls to http urls for link generations
        for module in bower_configs
            module.http_url = module.repository.url.replace("git://", "http://")
        # todo should get that info from data api
        $scope.config =
                bbversion: "0.9.0"
                txversion: "11.0.0"
                projectname: "cool project"
                projectversion: "0.0.1"
                projecturl: "http://buildbot.net"
                config: config
        $scope.bower_configs = bower_configs

]
