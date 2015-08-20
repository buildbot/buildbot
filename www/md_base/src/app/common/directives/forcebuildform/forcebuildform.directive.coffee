class ForcebuildForm extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/buildstep.html'
            controller: '_ForcebuildFormController'
            controllerAs: 'form'
            bindToController: true
            scope:
                fields: '='
        }

class _ForcebuildForm extends Controller
