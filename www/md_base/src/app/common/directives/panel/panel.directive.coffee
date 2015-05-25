class Panel extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/panel.html'
            controller: '_PanelController'
            controllerAs: 'panel'
            bindToController: true
            scope:
                name: '='
                title: '='
                isCollapsed: '='
                template: '='
                locked: '='
        }


class _Panel extends Controller

    constructor: (@$element, @$scope, $compile) ->
        # The following watch statement is necessary as the collapse function
        # is done by toggleClass in this controller instead of binding in template.
        @$scope.$watch 'panel.isCollapsed', (=> @updateCollapse())

        if @name
            tag = @name.replace /_/g, '-'
            content = @$element.children().eq(0).children().eq(1)
            content.html("<#{tag}></#{tag}>")
            $compile(content.contents())(@$scope)

    toggleCollapse: ->
        @isCollapsed = !@isCollapsed
        return

    updateCollapse: ->
        if @isCollapsed
            @$element.addClass('collapsed')
        else
            @$element.removeClass('collapsed')
