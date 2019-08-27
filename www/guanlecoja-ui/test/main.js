/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
if (typeof __karma__ === 'undefined' || __karma__ === null) {
    window.describe = function() {};
}

// define sample application logic

const m = angular.module("app", ["guanlecoja.ui", "ngSanitize"]);
const README = "https://github.com/tardyp/guanlecoja-ui/blob/master/Readme.md";
m.config(function($stateProvider, glMenuServiceProvider, $urlRouterProvider) {
        let group;
        $urlRouterProvider.otherwise('/bugcab');
        const groups = [];
        for (let i of ["cab", "camera", "bug", "calendar", "ban", "archive", "edit"]) {
            group = {
                name: i,
                items: []
            };
            for (let j of ["cab", "camera", "bug", "calendar", "ban", "archive", "edit"]) {
                group.items.push({
                    name: i + j});
                if (i === "bug") {
                    break;
                }
            }
            groups.push(group);
            glMenuServiceProvider.addGroup({
                name: group.name,
                caption: _.capitalize(group.name),
                icon: group.name,
                order: group.name.length
            });
        }

        glMenuServiceProvider.setFooter([{
            caption: "Github",
            href: "https://github.com/tardyp/guanlecoja-ui"
        }
        , {
            caption: "Help",
            href: README
        }
        , {
            caption: "About",
            href: README
        }
        ]);
        glMenuServiceProvider.setAppTitle("Guanlecoja-UI");
        return (() => {
            const result = [];
            for (group of Array.from(groups)) {
                result.push((() => {
                    const result1 = [];
                    for (let item of Array.from(group.items)) {
                        const state = {
                            controller: "dummyController",
                            template: `<div class='container'><div btf-markdown ng-include=\"'Readme.md'\"> \
        </div></div>`,
                            name: item.name,
                            url: `/${item.name}`,
                            data: {
                                group: group.name,
                                caption: _.capitalize(item.name)
                            }
                        };
                        result1.push($stateProvider.state(state));
                    }
                    return result1;
                })());
            }
            return result;
        })();
});

m.controller("dummyController", function($scope, $state, glBreadcrumbService, glNotificationService,
                                 glTopbarContextualActionsService) {

    // You can set different actions given the route
    glTopbarContextualActionsService.setContextualActions([{
        caption: "Download Doc",
        icon: "download",
        action() { return document.location = 'Readme.md'; }
    }
    , {
        caption: "View on Github",
        icon: "github",
        help: "Go to the github page of guanleoja-ui",
        action() { return document.location = README; }
    }
    , {
        icon: "google-plus",
        action() { return document.location = "https://plus.google.com"; }
    }
        ]);
    $scope.stateName = $state.current.name;
    glNotificationService.notify({msg:`You just transitioned to ${$scope.stateName}!`},
                                {title:"State transitions", group:"state"});

    glBreadcrumbService.setBreadcrumb([
        {caption: _.capitalize($state.current.data.group)}
    , {
        caption: _.capitalize($state.current.name),
        sref: $state.current.name
    }
    ]);
});
//
// angular-markdown-directive v0.3.0
// (c) 2013-2014 Brian Ford http://briantford.com
// License: MIT

m.provider("markdownConverter", function() {
  let opts = {};
  return {
      config(newOpts) {
        opts = newOpts;
    },

      $get() {
        return new Showdown.converter(opts);
    }
  };
}).directive("btfMarkdown", ($sanitize, markdownConverter) =>
  ({
      restrict: "AE",
      link(scope, element, attrs) {
        if (attrs.btfMarkdown) {
          scope.$watch(attrs.btfMarkdown, function(newVal) {
            const html = (newVal ? $sanitize(markdownConverter.makeHtml(newVal)) : "");
            element.html(html);
          });

        } else {
          const html = $sanitize(markdownConverter.makeHtml(element.text()));
          element.html(html);
      }
    }
  })
);
