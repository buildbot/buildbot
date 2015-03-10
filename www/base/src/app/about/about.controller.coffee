class About extends Controller
    constructor: ($scope, config, buildbotService) ->

        $scope.config = config

        #$scope.bower_configs = bower_configs
        buildbotService.all('application.spec').getList().then (specs) ->
            $scope.specs = specs
