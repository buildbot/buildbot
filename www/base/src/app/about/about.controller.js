class About {
    constructor($scope, config, restService) {

        $scope.config = config;

        restService.get('application.spec').then(specs => $scope.specs = specs['specs']);
    }
}


angular.module('app')
.controller('aboutController', ['$scope', 'config', 'restService', About]);
