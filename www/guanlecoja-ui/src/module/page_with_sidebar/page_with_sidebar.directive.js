/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class GlPageWithSidebar {
    constructor() {
        return {
            replace: true,
            transclude: true,
            restrict: 'E',
            scope: false,
            controllerAs: "page",
            template: require('./page_with_sidebar.tpl.jade'),
            controller: "_glPageWithSidebarController"
        };
    }
}

class _glPageWithSidebar {
    constructor($scope, glMenuService, $timeout, $window) {

        // by default, pin sidebar only if window is wide enough (collapse by default if narrow)
        this.$scope = $scope;
        this.$timeout = $timeout;
        this.$window = $window;
        this.sidebarPinned = this.$window.innerWidth > 800;
        // If user has previously pinned or unpinned the sidebar, use the saved value from localStorage
        const sidebarWasPinned = this.$window.localStorage.sidebarPinned;
        if ( (sidebarWasPinned === "true") || (sidebarWasPinned === "false") ) { // note -- localstorage only stores strings,  converts bools to string.
            this.sidebarPinned = sidebarWasPinned !== "false";
        }

        this.groups = glMenuService.getGroups();
        this.footer = glMenuService.getFooter();
        this.appTitle = glMenuService.getAppTitle();
        this.activeGroup = glMenuService.getDefaultGroup();
        this.inSidebar = false;
        this.sidebarActive = this.sidebarPinned;
    }

    toggleSidebarPinned() {
        this.sidebarPinned=!this.sidebarPinned;
        this.$window.localStorage.sidebarPinned = this.sidebarPinned.toString();
    }

    toggleGroup(group) {
        if (this.activeGroup !== group) {
            this.activeGroup = group;
        } else {
            this.activeGroup = null;
        }
    }

    enterSidebar() {
        this.inSidebar = true;
    }

    hideSidebar() {
        this.sidebarActive = false;
        this.inSidebar = false;
    }

    leaveSidebar() {
        this.inSidebar = false;
        if (this.timeout != null) {
            this.$timeout.cancel(this.timeout);
            this.timeout = undefined;
        }
        this.timeout = this.$timeout((() => {
            if (!this.inSidebar && !this.sidebarPinned) {
                this.sidebarActive = false;
                this.activeGroup = null;
            }
        }
            ), 500);
    }
}


angular.module('guanlecoja.ui')
.directive('glPageWithSidebar', [GlPageWithSidebar])
.controller('_glPageWithSidebarController', ['$scope', 'glMenuService', '$timeout', '$window', _glPageWithSidebar]);
