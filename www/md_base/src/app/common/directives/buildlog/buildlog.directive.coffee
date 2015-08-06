class BuildLog extends Directive

    constructor: ->
        return {
            restrict: 'E'
            controller: '_BuildLogController'
            controllerAs: 'log'
            bindToController: true
            scope:
                log: '='
        }

class _BuildLog extends Controller
    lines: 0
    contentsLength: 0

    constructor: ($scope, $element) ->
        # Using directly DOM maniplution instead of ng-repeat to improve page performance
        @codeTable = angular.element('<table></table>')
        $element.append(@codeTable)

        # Binding contents watch functions
        @contents = @log.loadContents().getArray()
        $scope.$watch 'log.contents.length', => @updateContents()

    addLine: (lineno, line) ->
        @codeTable.append """
        <tr>
            <td class="lineno no-select">#{lineno}</td>
            <td class="code"><span>#{line}</span></td>
        </tr>
        """

    updateContents: ->
        while @contentsLength < @contents.length
            content = @contents[@contentsLength++]
            firstline = content.firstline
            lines = content.content.split('\n')

            lines.pop() if lines.length > 0 # pop one line as the content will contain a tailing '\n'

            @lines = firstline + 1
            for line in lines
                @addLine @lines++, line
