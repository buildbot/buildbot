/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class GlNotification {
    constructor() {
        return {
            replace: true,
            transclude: true,
            restrict: 'E',
            scope: false,
            controllerAs: "n",
            template: require('./notification.tpl.jade'),
            controller: "_glNotificationController"
        };
    }
}

class _glNotification {

    constructor($scope, glNotificationService) {
        this.$scope = $scope;
        this.glNotificationService = glNotificationService;
        this.notifications = this.glNotificationService.notifications;
        null;
    }

    dismiss(id, e) {
        this.glNotificationService.dismiss(id);
        e.stopPropagation();
        return null;
    }
}


angular.module('guanlecoja.ui')
.directive('glNotification', [GlNotification])
.controller('_glNotificationController', ['$scope', 'glNotificationService', _glNotification]);