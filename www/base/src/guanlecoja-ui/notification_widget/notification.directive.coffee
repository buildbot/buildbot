class GlNotification extends Directive
    constructor: ->
        return {
            replace: true
            transclude: true
            restrict: 'E'
            scope: false
            controllerAs: "n"
            templateUrl: "views/notification.html"
            controller: "_glNotificationController"
        }

class _glNotification extends Controller

    constructor: (@$scope, @glNotificationService) ->
        @notifications = @glNotificationService.notifications
        null

    dismiss: (id, e) ->
        @glNotificationService.dismiss(id)
        e.stopPropagation()
        null
