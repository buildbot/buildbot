class Changelist extends Directive('common')
    constructor: ->
        return {
            replace: true
            restrict: 'E'
            scope: {changes: '='}
            templateUrl: 'views/changelist.html'
            controller: '_changeListController'
        }

class _changeList extends Controller('common')
    constructor: ($scope, dataUtilsService) ->

        formatAuthor = (change) ->
            email = dataUtilsService.emailInString(change.author)
            # Remove email from author string
            if email && change.author.split(' ').length > 0
                change.author_name = change.author.replace(///\s<#{email}>///, '')
                change.author_email = email

        $scope.$watch 'changes', (changes) ->
            if changes?
                for change in changes
                    formatAuthor(change)
        , true

        $scope.expandDetails = ->
            for change in $scope.changes
                change.show_details = true

        $scope.collapseDetails = ->
            for change in $scope.changes
                change.show_details = false
