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

    constructor: (@$scope, @$attrs, @menuService) ->
        @items = @menuService.getItems()
    
    isHighlighted: (name) ->
        return name == @menuService.getCurrent()
