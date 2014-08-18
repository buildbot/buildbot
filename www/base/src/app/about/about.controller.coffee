class About extends Controller
    constructor: ($scope, config, buildbotService) ->
        # translate github urls to http urls for link generations
        #for module in bower_configs
        #    module.http_url = module.repository?.url?.replace("git://", "http://")
        # todo should get that info from data api
        $scope.config =
            bbversion: "0.9.0"
            txversion: "11.0.0"
            projectname: "cool project"
            projectversion: "0.0.1"
            projecturl: "http://buildbot.net"
            config: config
        #$scope.bower_configs = bower_configs
        buildbotService.all('application.spec').getList().then (specs) ->
            $scope.specs = specs
