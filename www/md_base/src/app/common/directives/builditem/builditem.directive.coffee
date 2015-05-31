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
    constructor: (buildbotService) ->
        # TODO: add links to builders and builds after the corresponding pages has finished
        if @outBuilder
            @builder = outBuilder
        else if @showBuilder
            buildbotService.one('builders', @build.builderid).get().then (data) =>
                @builder = data


