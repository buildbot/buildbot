# base widget handling has-error, and error message popups
class Basefield extends Directive('common')
    constructor: ->
        return {
            replace: true
            transclude: true
            restrict: 'E'
            scope: true
            templateUrl: "views/basefield.html"
            controller: '_basefieldController'
        }

class _basefield extends Controller('common')
    constructor: ($scope) ->
        # clear error on value change
        $scope.$watch "field.value", (o,n) ->
            $scope.field.errors = ""
