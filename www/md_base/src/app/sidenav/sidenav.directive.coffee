class Sidenav extends Directive

    constructor: ->
        return {
            require: 'mdSidenav'
            restrict: 'E'
            replace: true
            templateUrl: 'views/sidenav.html'
            controller: '_SidenavController'
            controllerAs: 'sidenav'
        }


class _Sidenav extends Controller

    items: []
    current: ''

    constructor: (@$scope, @$attrs) ->
        @$scope.$watch $attrs.items, (newItems) =>
            @items = newItems

        @$scope.$watch $attrs.current, (newCurrent) =>
            @current = newCurrent
    
    isHighlighted: (name) ->
        return name == @current
