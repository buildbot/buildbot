/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class glNotification {
    constructor($rootScope, $timeout) {
        this.$rootScope = $rootScope;
        this.$timeout = $timeout;
        this.notifications = [];
        this.curid = 0;
        null;
    }

    notify(opts) {
        this.curid += 1;
        if (opts.title == null) { opts.title = "Info"; }
        opts.id = this.curid;
        let id = this.curid;
        if (opts.group != null) {
            for (let i in this.notifications) {
                const n = this.notifications[i];
                if (opts.group === n.group) {
                    id = i;
                    n.msg += `\n${opts.msg}`;
                }
            }
        }
        if (id === this.curid) {
            this.notifications.push(opts);
        }
        return null;
    }

    // some shortcuts...
    error(opts) {
        if (opts.title == null) { opts.title = "Error"; }
        return this.notify(opts);
    }

    network(opts) {
        if (opts.title == null) { opts.title = "Network issue"; }
        if (opts.group == null) { opts.group = "Network"; }
        return this.notify(opts);
    }

    dismiss(id) {
        for (let i in this.notifications) {
            const n = this.notifications[i];
            if (n.id === id) {
                this.notifications.splice(i, 1);
                return null;
            }
        }
        return null;
    }
}


angular.module('guanlecoja.ui')
.service('glNotificationService', ['$rootScope', '$timeout', glNotification]);
