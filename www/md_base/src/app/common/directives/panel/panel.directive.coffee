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
                isCollapsed: '='
        }


class _Panel extends Controller

    constructor: (@$element, @$scope) ->
        @$scope.$watch 'panel.isCollapsed', (=> @updateCollapse())

    toggleCollapse: ->
        @isCollapsed = !@isCollapsed
        return

    updateCollapse: ->
        if @isCollapsed
            @$element.addClass('collapsed')
        else
            @$element.removeClass('collapsed')
