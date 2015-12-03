class BuildLog extends Directive

    constructor: ->
        return {
            restrict: 'E'
            controller: '_BuildLogController'
            controllerAs: 'log'
            bindToController: true
            scope:
                raw_log: '=log'
        }

class _BuildLog extends Controller
    lines: 0
    contents: []
    contentsLength: 0

    constructor: (@$scope, @$element, @$sanitize) ->
        # Using directly DOM maniplution instead of ng-repeat to improve page performance
        @codeTable = angular.element('<table></table>')
        @$element.append(@codeTable)

        # Refresh contents if log is changed
        @$scope.$watch 'log.raw_log', => @bindContents()
        @$scope.$watch 'log.contents.length', => @updateContents()

    bindContents: ->

        # Restore initial state
        @lines = 0
        @contents = []
        @contentsLength = 0
        @codeTable.html('')

        # Load and process contents
        @log = @raw_log
        @contents = @log.contents or @log.loadContents().getArray()
        @updateContents()

    addLine: (lineno, line) ->
        @codeTable.append """
        <tr>
            <td class="lineno no-select">#{lineno}</td>
            <td class="code"><span>#{@$sanitize(line)}</span></td>
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
