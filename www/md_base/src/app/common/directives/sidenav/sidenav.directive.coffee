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

    constructor: (@$scope, @menuService) ->
    
    isHighlighted: (name) ->
        return @menuService.getCurrent().indexOf(name) == 0

    getItems: ->
        return @menuService.getItems()
