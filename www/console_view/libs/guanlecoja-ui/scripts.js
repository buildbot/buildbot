(function() {
  angular.module("guanlecoja.ui", ["ui.bootstrap", "ui.router", "ngAnimate"]);

}).call(this);

(function() {
  var glBreadcrumb;

  glBreadcrumb = (function() {
    function glBreadcrumb($rootScope) {
      this.$rootScope = $rootScope;
      ({});
    }

    glBreadcrumb.prototype.setBreadcrumb = function(breadcrumb) {
      return this.$rootScope.$broadcast("glBreadcrumb", breadcrumb);
    };

    return glBreadcrumb;

  })();

  angular.module('guanlecoja.ui').service('glBreadcrumbService', ['$rootScope', glBreadcrumb]);

}).call(this);

(function() {
  var GlMenu;

  GlMenu = (function() {
    function GlMenu() {
      this.groups = {};
      this.defaultGroup = null;
      this.footer = [];
    }

    GlMenu.prototype.appTitle = "set AppTitle using GlMenuServiceProvider.setAppTitle";

    GlMenu.prototype.addGroup = function(group) {
      group.items = [];
      if (group.order == null) {
        group.order = 99;
      }
      this.groups[group.name] = group;
      return this.groups;
    };

    GlMenu.prototype.setDefaultGroup = function(group) {
      return this.defaultGroup = group;
    };

    GlMenu.prototype.setFooter = function(footer) {
      return this.footer = footer;
    };

    GlMenu.prototype.setAppTitle = function(title) {
      return this.appTitle = title;
    };

    GlMenu.prototype.$get = [
      "$state", function($state) {
        var group, groups, i, item, len, name, ref, ref1, self, state;
        ref = $state.get().slice(1);
        for (i = 0, len = ref.length; i < len; i++) {
          state = ref[i];
          group = state.data.group;
          if (group == null) {
            continue;
          }
          if (!this.groups.hasOwnProperty(group)) {
            throw Error("group " + group + " has not been defined with glMenuProvider.group(). has: " + (_.keys(this.groups)));
          }
          this.groups[group].items.push({
            caption: state.data.caption || _.capitalize(state.name),
            sref: state.name
          });
        }
        ref1 = this.groups;
        for (name in ref1) {
          group = ref1[name];
          if (group.items.length === 0 && !group.separator) {
            delete this.groups[name];
          } else if (group.items.length === 1) {
            item = group.items[0];
            group.caption = item.caption;
            group.sref = item.sref;
            group.items = [];
          } else {
            group.sref = ".";
          }
        }
        groups = _.values(this.groups);
        groups.sort(function(a, b) {
          return a.order - b.order;
        });
        self = this;
        return {
          getGroups: function() {
            return groups;
          },
          getDefaultGroup: function() {
            return self.defaultGroup;
          },
          getFooter: function() {
            return self.footer;
          },
          getAppTitle: function() {
            return self.appTitle;
          }
        };
      }
    ];

    return GlMenu;

  })();

  angular.module('guanlecoja.ui').provider('glMenuService', [GlMenu]);

}).call(this);

(function() {
  var glHttpInterceptor;

  glHttpInterceptor = (function() {
    function glHttpInterceptor(glNotificationService, $q, $timeout) {
      return function(promise) {
        var errorHandler;
        errorHandler = function(res) {
          var e, error, msg;
          try {
            msg = (res.status + ":" + res.data.error + " ") + ("when:" + res.config.method + " " + res.config.url);
          } catch (error) {
            e = error;
            msg = res.toString();
          }
          $timeout((function() {
            return glNotificationService.network(msg);
          }), 100);
          return $q.reject(res);
        };
        return promise.then(angular.identity, errorHandler);
      };
    }

    return glHttpInterceptor;

  })();

  angular.module('guanlecoja.ui').factory('glHttpInterceptor', ['glNotificationService', '$q', '$timeout', glHttpInterceptor]);

}).call(this);

(function() {
  var glNotification;

  glNotification = (function() {
    function glNotification($rootScope, $timeout) {
      this.$rootScope = $rootScope;
      this.$timeout = $timeout;
      this.notifications = [];
      this.curid = 0;
      null;
    }

    glNotification.prototype.notify = function(opts) {
      var i, id, n, ref;
      this.curid += 1;
      if (opts.title == null) {
        opts.title = "Info";
      }
      opts.id = this.curid;
      id = this.curid;
      if (opts.group != null) {
        ref = this.notifications;
        for (i in ref) {
          n = ref[i];
          if (opts.group === n.group) {
            id = i;
            n.msg += "\n" + opts.msg;
          }
        }
      }
      if (id === this.curid) {
        this.notifications.push(opts);
      }
      return null;
    };

    glNotification.prototype.error = function(opts) {
      if (opts.title == null) {
        opts.title = "Error";
      }
      return this.notify(opts);
    };

    glNotification.prototype.network = function(opts) {
      if (opts.title == null) {
        opts.title = "Network issue";
      }
      if (opts.group == null) {
        opts.group = "Network";
      }
      return this.notify(opts);
    };

    glNotification.prototype.dismiss = function(id) {
      var i, n, ref;
      ref = this.notifications;
      for (i in ref) {
        n = ref[i];
        if (n.id === id) {
          this.notifications.splice(i, 1);
          return null;
        }
      }
      return null;
    };

    return glNotification;

  })();

  angular.module('guanlecoja.ui').service('glNotificationService', ['$rootScope', '$timeout', glNotification]);

}).call(this);

(function() {
  var GlPageWithSidebar, _glPageWithSidebar;

  GlPageWithSidebar = (function() {
    function GlPageWithSidebar() {
      return {
        replace: true,
        transclude: true,
        restrict: 'E',
        scope: false,
        controllerAs: "page",
        templateUrl: "guanlecoja.ui/views/page_with_sidebar.html",
        controller: "_glPageWithSidebarController"
      };
    }

    return GlPageWithSidebar;

  })();

  _glPageWithSidebar = (function() {
    function _glPageWithSidebar($scope, glMenuService, $timeout, $window) {
      this.$scope = $scope;
      this.$timeout = $timeout;
      this.$window = $window;
      this.sidebarPinned = this.$window.innerWidth > 800;
      this.groups = glMenuService.getGroups();
      this.footer = glMenuService.getFooter();
      this.appTitle = glMenuService.getAppTitle();
      this.activeGroup = glMenuService.getDefaultGroup();
      this.inSidebar = false;
      this.sidebarActive = this.sidebarPinned;
    }

    _glPageWithSidebar.prototype.toggleGroup = function(group) {
      if (this.activeGroup !== group) {
        return this.activeGroup = group;
      } else {
        return this.activeGroup = null;
      }
    };

    _glPageWithSidebar.prototype.enterSidebar = function() {
      this.sidebarActive = true;
      return this.inSidebar = true;
    };

    _glPageWithSidebar.prototype.hideSidebar = function() {
      this.sidebarActive = false;
      return this.inSidebar = false;
    };

    _glPageWithSidebar.prototype.leaveSidebar = function() {
      this.inSidebar = false;
      if (this.timeout != null) {
        this.$timeout.cancel(this.timeout);
        this.timeout = void 0;
      }
      return this.timeout = this.$timeout(((function(_this) {
        return function() {
          if (!(_this.inSidebar || _this.sidebarPinned)) {
            _this.sidebarActive = false;
            return _this.activeGroup = null;
          }
        };
      })(this)), 500);
    };

    return _glPageWithSidebar;

  })();

  angular.module('guanlecoja.ui').directive('glPageWithSidebar', [GlPageWithSidebar]).controller('_glPageWithSidebarController', ['$scope', 'glMenuService', '$timeout', '$window', _glPageWithSidebar]);

}).call(this);

(function() {
  var GlNotification, _glNotification;

  GlNotification = (function() {
    function GlNotification() {
      return {
        replace: true,
        transclude: true,
        restrict: 'E',
        scope: false,
        controllerAs: "n",
        templateUrl: "guanlecoja.ui/views/notification.html",
        controller: "_glNotificationController"
      };
    }

    return GlNotification;

  })();

  _glNotification = (function() {
    function _glNotification($scope, glNotificationService) {
      this.$scope = $scope;
      this.glNotificationService = glNotificationService;
      this.notifications = this.glNotificationService.notifications;
      null;
    }

    _glNotification.prototype.dismiss = function(id, e) {
      this.glNotificationService.dismiss(id);
      e.stopPropagation();
      return null;
    };

    return _glNotification;

  })();

  angular.module('guanlecoja.ui').directive('glNotification', [GlNotification]).controller('_glNotificationController', ['$scope', 'glNotificationService', _glNotification]);

}).call(this);

(function() {
  var GlTopbarContextualActions, _glTopbarContextualActions, glTopbarContextualActions;

  GlTopbarContextualActions = (function() {
    function GlTopbarContextualActions() {
      return {
        replace: true,
        restrict: 'E',
        scope: true,
        templateUrl: "guanlecoja.ui/views/topbar-contextual-actions.html",
        controller: "_glTopbarContextualActionsController"
      };
    }

    return GlTopbarContextualActions;

  })();

  _glTopbarContextualActions = (function() {
    function _glTopbarContextualActions($scope, $sce) {
      $scope.$on("$stateChangeStart", function(ev, state) {
        return $scope.actions = [];
      });
      $scope.$on("glSetContextualActions", function(e, data) {
        var i, item, len;
        for (i = 0, len = data.length; i < len; i++) {
          item = data[i];
          if (item.extra_class == null) {
            item.extra_class = "";
          }
        }
        return $scope.actions = data;
      });
    }

    return _glTopbarContextualActions;

  })();

  glTopbarContextualActions = (function() {
    function glTopbarContextualActions($rootScope) {
      this.$rootScope = $rootScope;
      ({});
    }

    glTopbarContextualActions.prototype.setContextualActions = function(actions) {
      return this.$rootScope.$broadcast("glSetContextualActions", actions);
    };

    return glTopbarContextualActions;

  })();

  angular.module('guanlecoja.ui').directive('glTopbarContextualActions', [GlTopbarContextualActions]).controller('_glTopbarContextualActionsController', ['$scope', '$sce', _glTopbarContextualActions]).service('glTopbarContextualActionsService', ['$rootScope', glTopbarContextualActions]);

}).call(this);

(function() {
  var GlTopbar, _glTopbar;

  GlTopbar = (function() {
    function GlTopbar() {
      return {
        replace: true,
        transclude: true,
        restrict: 'E',
        scope: false,
        controllerAs: "page",
        templateUrl: "guanlecoja.ui/views/topbar.html",
        controller: "_glTopbarController"
      };
    }

    return GlTopbar;

  })();

  _glTopbar = (function() {
    function _glTopbar($scope, glMenuService, $location) {
      var groups;
      groups = glMenuService.getGroups();
      groups = _.zipObject(_.map(groups, function(g) {
        return g.name;
      }), groups);
      $scope.appTitle = glMenuService.getAppTitle();
      $scope.$on("$stateChangeStart", function(ev, state) {
        var ref, ref1, ref2;
        $scope.breadcrumb = [];
        if (((ref = state.data) != null ? ref.group : void 0) && ((ref1 = state.data) != null ? ref1.caption : void 0) !== groups[state.data.group].caption) {
          $scope.breadcrumb.push({
            caption: groups[state.data.group].caption
          });
        }
        return $scope.breadcrumb.push({
          caption: ((ref2 = state.data) != null ? ref2.caption : void 0) || _.capitalize(state.name),
          href: '#' + $location.hash()
        });
      });
      $scope.$on("glBreadcrumb", function(e, data) {
        return $scope.breadcrumb = data;
      });
    }

    return _glTopbar;

  })();

  angular.module('guanlecoja.ui').directive('glTopbar', [GlTopbar]).controller('_glTopbarController', ['$scope', 'glMenuService', '$location', _glTopbar]);

}).call(this);

angular.module("guanlecoja.ui").run(["$templateCache", function($templateCache) {$templateCache.put("guanlecoja.ui/views/page_with_sidebar.html","<div class=\"gl-page-with-sidebar\" ng-class=\"{\'active\': page.sidebarActive, \'pinned\': page.sidebarPinned}\"><div class=\"sidebar sidebar-blue\" ng-mouseenter=\"page.enterSidebar()\" ng-mouseleave=\"page.leaveSidebar()\"><ul><li class=\"sidebar-main\"><a href=\"javascript:\">{{page.appTitle}}<span class=\"menu-icon fa fa-bars\" ng-hide=\"page.sidebarActive\" ng-click=\"page.sidebarActive=!page.sidebarActive\"></span><span class=\"menu-icon fa fa-thumb-tack\" ng-show=\"page.sidebarActive\" ng-click=\"page.sidebarPinned=!page.sidebarPinned\" ng-class=\"{\'fa-45\': !page.sidebarPinned}\"></span></a></li><li class=\"sidebar-title\"><span>NAVIGATION</span></li><div ng-repeat=\"group in page.groups\"><div ng-if=\"group.items.length &gt; 0\"><li class=\"sidebar-list\"><a ng-click=\"page.toggleGroup(group)\"><i class=\"fa fa-angle-right\"></i>&nbsp;{{group.caption}}<span class=\"menu-icon fa\" ng-class=\"\'fa-\' + group.icon\"></span></a></li><li class=\"sidebar-list subitem\" ng-class=\"{\'active\': page.activeGroup==group}\" ng-repeat=\"item in group.items\"><a ui-sref=\"{{item.sref}}\" ng-click=\"page.hideSidebar()\">{{item.caption}}</a></li></div><div ng-if=\"group.items.length == 0\"><div ng-if=\"group.separator\"><li class=\"sidebar-title\"><span>{{group.caption}}</span></li></div><div ng-if=\"!group.separator\"><li class=\"sidebar-separator\" ng-if=\"!$first\"></li><li class=\"sidebar-list\"><a ui-sref=\"{{group.sref}}\" ng-click=\"page.toggleGroup(group)\">{{group.caption}}<span class=\"menu-icon fa\" ng-class=\"\'fa-\' + group.icon\"></span></a></li></div></div></div></ul><div class=\"sidebar-footer\"><div class=\"col-xs-4\" ng-repeat=\"item in page.footer\"><a ng-href=\"{{item.href}}\">{{item.caption}}</a></div></div></div><div class=\"content\"><div ng-transclude=\"ng-transclude\"></div></div></div>");
$templateCache.put("guanlecoja.ui/views/notification.html","<li class=\"dropdown notifications\" uib-dropdown=\"uib-dropdown\"><a uib-dropdown-toggle=\"uib-dropdown-toggle\"><i class=\"fa fa-bell-o fa-lg\" ng-class=\"{\'fa-ringing\': n.notifications.length &gt; 0 }\"></i></a><ul class=\"uib-dropdown-menu dropdown-menu dropdown-menu-right\" dropdown-toggle=\"dropdown-toggle\"><li class=\"dropdown-header\">Notifications</li><li class=\"divider\"></li><div ng-repeat=\"msg in n.notifications\"><li><div class=\"item\"><button class=\"close\" ng-click=\"n.dismiss(msg.id, $event)\">&times;</button><div class=\"title\">{{msg.title}}:</div><div class=\"msg\">{{msg.msg}}</div></div></li><li class=\"divider\"></li></div><li ng-hide=\"n.notifications.length&gt;0\"><div class=\"item\"><small class=\"msg\"> all caught up!</small></div></li></ul></li>");
$templateCache.put("guanlecoja.ui/views/topbar-contextual-actions.html","<form class=\"navbar-form navbar-left\"><span ng-repeat=\"a in actions\"><button class=\"btn btn-default\" type=\"button\" ng-class=\"a.extra_class\" ng-click=\"a.action()\" title=\"{{a.help}}\"><i class=\"fa\" ng-if=\"a.icon\" ng-class=\"\'fa-\' + a.icon\"></i><span ng-if=\"a.icon&amp;&amp;a.caption\">&nbsp;</span>{{::a.caption}}</button>&nbsp;</span></form>");
$templateCache.put("guanlecoja.ui/views/topbar.html","<div class=\"navbar navbar-default navbar-static-top\"><div class=\"container-fluid\"><a class=\"navbar-brand\">{{appTitle}}</a><ol class=\"breadcrumb\"><li ng-repeat=\"b in breadcrumb\"><a ng-if=\"b.sref\" ui-sref=\"{{b.sref}}\">{{b.caption}}</a><a ng-if=\"b.href\" ng-href=\"{{b.href}}\">{{b.caption}}</a><span ng-if=\"b.href == undefined &amp;&amp; b.sref == undefined\" ng-href=\"{{b.href}}\">{{b.caption}}</span></li></ol><ul class=\"nav navbar-nav pull-right\" ng-transclude=\"ng-transclude\"></ul></div></div>");}]);
//# sourceMappingURL=scripts.js.map
