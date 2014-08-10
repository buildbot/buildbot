class GlTopbar extends Directive
    constructor: ->
        return {
            replace: true
            transclude: true
            restrict: 'E'
            scope: false
            controllerAs: "page"
            templateUrl: "guanlecoja.ui/views/topbar.html"
            controller: "_glTopbarController"
        }

class _glTopbar extends Controller
    constructor: ($scope) ->
        null
