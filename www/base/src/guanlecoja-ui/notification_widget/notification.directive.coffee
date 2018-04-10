class GlNotification
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

class _glNotification

    constructor: (@$scope, @glNotificationService) ->
        @notifications = @glNotificationService.notifications
        null

    dismiss: (id, e) ->
        @glNotificationService.dismiss(id)
        e.stopPropagation()
        null


angular.module('guanlecoja.ui')
.directive('glNotification', [GlNotification])
.controller('_glNotificationController', ['$scope', 'glNotificationService', _glNotification])
