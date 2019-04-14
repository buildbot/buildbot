class About
    constructor: ($scope, config, restService) ->

        $scope.config = config
        $scope.bower_configs = BOWERDEPS

        #$scope.bower_configs = bower_configs
        restService.get('application.spec').then (specs) ->
            $scope.specs = specs['specs']


angular.module('app')
.controller('aboutController', ['$scope', 'config', 'restService', About])