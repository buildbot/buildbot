class Panel extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/panel.html'
            controller: '_PanelController'
            controllerAs: 'panel'
            bindToController: true
            scope:
                # Using bind directly to avoid `title` attr on the element which lead to showing a tooltip
                # This also makes the interface more simpler for outsiders.
                bind: '='
                locked: '='
        }


class _Panel extends Controller

    constructor: (@$element, @$scope, $compile) ->
        # The following watch statement is necessary as the collapse function
        # is done by toggleClass in this controller instead of binding in template.
        @$scope.$watch 'panel.bind.collapsed', => @updateCollapse()

        if @bind.name
            tag = @bind.name.replace /_/g, '-'
            content = @$element.children().eq(0).children().eq(1)
            content.html("<#{tag}></#{tag}>")
            $compile(content.contents())(@$scope)

    toggleCollapse: ->
        @bind.collapsed = !@bind.collapsed
        return

    updateCollapse: ->
        if @bind.collapsed
            @$element.addClass('collapsed')
        else
            @$element.removeClass('collapsed')
