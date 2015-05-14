class Panel extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/panel.html'
            controller: '_PanelController'
            controllerAs: 'panel'
            transclude: true
            bindToController: true
            scope:
                title: '@'
        }


class _Panel extends Controller

    isCollapsed: false

    constructor: (@$element) ->

    toggleCollapse: ->
        @isCollapsed = !@isCollapsed
        @$element.toggleClass('collapsed')
        return
