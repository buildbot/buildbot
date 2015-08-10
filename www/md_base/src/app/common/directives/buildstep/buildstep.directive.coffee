class BuildStep extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/buildstep.html'
            controller: '_BuildStepController'
            controllerAs: 'buildstep'
            bindToController: true
            scope:
                step: '='
        }

class _BuildStep extends Controller
    duration: 0
    selectedLog: null
    isExpanded: false

    constructor: ($scope, RESULTS_TEXT) ->
        $scope.$watch 'buildstep.step', (=> @updateState(RESULTS_TEXT)), true
        @step.loadLogs()

    updateState: (RESULTS_TEXT) ->
        @updateDuration()

        if @step.complete is false and @step.started_at > 0
            @state_class = 'pending'
        else if @step.results == 0
            @state_class = 'success'
        else if @step.results >= 1 and @step.results <= 6
            @state_class = RESULTS_TEXT[@step.results].toLowerCase()
        else
            @state_class = 'unknown'

    updateDuration: ->
        if @step.complete
            @duration = @step.complete_at - @step.started_at
        else if @step.started_at > 0
            @duration = moment().unix() - @step.started_at
        else
            @duration = 0

        @duration = Math.round(@duration)

    toggleExpand: ->
        if @isExpanded
            @isExpanded = false
        else if @step?.logs?.length > 0
            @isExpanded = true
            @selectedLog = @step.logs[0] if not @selectedLog
