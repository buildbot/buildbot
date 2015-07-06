class ChangeItem extends Directive

    constructor: ->
        return {
            restrict: 'E'
            templateUrl: 'views/changeitem.html'
            controller: '_ChangeItemController'
            controllerAs: 'changeitem'
            bindToController: true
            scope:
                change: "="
        }

class _ChangeItem extends Controller
    showDetail: false

    toggleDetail: ->
        @showDetail = !@showDetail

    constructor: (dataService) ->
        @author = @change.author
        @revision = @change.revision[0...6]
        @comments = @change.comments
        @date = @change.when_timestamp
        @files = @change.files

        # Official W3C email regular expression
        emailRegex = /[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*/
        email = emailRegex.exec @author

        @email = email[0] if email

        @displayData =
            'Repository': @change.repository
            'Branch': @change.branch
            'Revision': @change.revision

