class bbcheckbox extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            restrict: 'E'
            transclude: true
            scope: {data:'=', isDisabled:'='}
            templateUrl: 'views/checkbox.html'
            controller: '_fieldController'
        }

class bbradio extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            restrict: 'E'
            transclude: true
            scope: {data:'=', isDisabled:'='}
            templateUrl: 'views/radio.html'
            controller: '_fieldController'
        }

class bbinput extends Directive('common')
    constructor: (RecursionHelper) ->
        return {
            restrict: 'E'
            replace: true
            transclude: true
            scope: {data:'=', isDisabled:'='}
            templateUrl: 'views/input.html'
            controller: '_fieldController'
        }

class _field extends Controller('common')
    constructor: ($scope) ->
        $scope.changeSettings  = (settings, value) -> 
            localStorage.setItem(settings, value)
