class Properties
    constructor: ->
        return {
            replace: true
            restrict: 'E'
            scope: {properties: '='}
            templateUrl: 'views/properties.html'
        }


angular.module('common')
.directive('properties', [Properties])