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

    updateDuration: ->
        if @step.complete_at > 0
            @duration = @step.complete_at - @step.started_at
            return
        else if @step.started_at > 0
            @duration = moment().unix() - @step.started_at
        else
            @duration = 0
        setTimeout (=> @updateDuration()), 500

    constructor: ->
        @updateDuration()

