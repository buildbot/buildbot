# base widget handling has-error, and error message popups
class Basefield
    constructor: ->
        return {
            replace: true
            transclude: true
            restrict: 'E'
            scope: true
            templateUrl: "views/basefield.html"
            controller: '_basefieldController'
        }


class _basefield
    constructor: ($scope) ->
        # clear error on value change
        $scope.$watch "field.value", (o,n) ->
            $scope.field.haserrors = false


angular.module('common')
.directive('basefield', [Basefield])
.controller('_basefieldController', ['$scope', _basefield])