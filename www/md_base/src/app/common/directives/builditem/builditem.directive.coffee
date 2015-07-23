class BuildItem extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/builditem.html'
            controller: '_BuildItemController'
            controllerAs: 'builditem'
            bindToController: true
            scope:
                build: '='
                outBuilder: '=builder'
                showBuilder: '='
        }

class _BuildItem extends Controller
    constructor: (dataService) ->
        # TODO: add links to builders and builds after the corresponding pages has finished
        if @outBuilder
            @builder = outBuilder
        else if @showBuilder
            dataService.getBuilders(@build.builderid, subscribe: false).then (builders) =>
                @builder = builders[0]
