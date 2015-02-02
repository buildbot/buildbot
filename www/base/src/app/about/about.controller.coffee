class About extends Controller
    constructor: ($scope, config, buildbotService) ->
        # todo should get that info from data api: see http://trac.buildbot.net/ticket/3175
        $scope.config =
            bbversion: "0.9.0"
            txversion: "11.0.0"
            projectname: config.title
            projecturl: config.titleURL
            config: config
        #$scope.bower_configs = bower_configs
        buildbotService.all('application.spec').getList().then (specs) ->
            $scope.specs = specs
