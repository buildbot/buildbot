class About extends Controller
    constructor: ($scope, config, restService) ->

        $scope.config = config

        #$scope.bower_configs = bower_configs
        restService.get('application.spec').then (specs) ->
            $scope.specs = specs
