class About extends Controller
    constructor: ($scope, config, buildbotService) ->
        versions = config.versions

        $scope.config = config
        $scope.versions = config.versions
        $scope.env_versions = config.env_versions

        #$scope.bower_configs = bower_configs
        buildbotService.all('application.spec').getList().then (specs) ->
            $scope.specs = specs
