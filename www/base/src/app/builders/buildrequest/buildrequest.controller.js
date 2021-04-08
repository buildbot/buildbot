/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class BuildrequestController {
    constructor($scope, dataService, $stateParams, findBuilds, glBreadcrumbService, glTopbarContextualActionsService, publicFieldsFilter) {
        $scope.is_cancelling = false;
        $scope.$watch("buildrequest.claimed", function(n, o) {
            if (n) {  // if it is unclaimed, then claimed, we need to try again
                findBuilds($scope, $scope.buildrequest.buildrequestid,
                           $stateParams.redirect_to_build);
                // when a build is discovered, force the tab to go to that build
                const savedNew = $scope.builds.onNew;
                $scope.builds.onNew = function(build) {
                    build.active = true;
                    savedNew(build);
                };
            }
        });

        const doCancel = function() {
            $scope.is_cancelling = true;
            refreshContextMenu();

            const success = function(res) {};
                // refresh is done via complete event

            const failure = function(why) {
                $scope.is_cancelling = false;
                $scope.error = `Cannot cancel: ${why.error.message}`;
                refreshContextMenu();
            };

            $scope.buildrequest.control('cancel').then(success, failure);
        };

        var refreshContextMenu = function() {
            const actions = [];
            if (($scope.buildrequest == null)) {
                return;
            }
            if (!$scope.buildrequest.complete) {
                if ($scope.is_cancelling) {
                    actions.push({
                       caption: "Cancelling...",
                       icon: "spinner fa-spin",
                       action: doCancel
                    });
                } else {
                    actions.push({
                       caption: "Cancel",
                       extra_class: "btn-default",
                       action: doCancel
                    });
                }
            }

            glTopbarContextualActionsService.setContextualActions(actions);
        };
        $scope.$watch('buildrequest.complete', refreshContextMenu);

        // Clear breadcrumb and contextual action buttons on destroy
        const clearGl = function () {
            glBreadcrumbService.setBreadcrumb([]);
            glTopbarContextualActionsService.setContextualActions([]);
        };
        $scope.$on('$destroy', clearGl);

        const data = dataService.open().closeOnDestroy($scope);
        data.getBuildrequests($stateParams.buildrequest).onNew = function(buildrequest) {
            $scope.buildrequest = buildrequest;
            $scope.raw_buildrequest = publicFieldsFilter(buildrequest);
            data.getBuilders(buildrequest.builderid).onNew = function(builder) {
                $scope.builder = builder;
                const breadcrumb = [{
                        caption: builder.name,
                        sref: `builder({builder:${buildrequest.builderid}})`
                    }
                    ,
                        {caption: "buildrequests"}
                    , {
                        caption: buildrequest.buildrequestid,
                        sref: `buildrequest({buildrequest:${buildrequest.buildrequestid}})`
                    }
                ];

                glBreadcrumbService.setBreadcrumb(breadcrumb);
            };

            data.getBuildsets(buildrequest.buildsetid).onNew = function(buildset) {
                $scope.buildset = publicFieldsFilter(buildset);
                buildset.getProperties().onNew  = properties => $scope.properties = publicFieldsFilter(properties);
            };
        };
    }
}


angular.module('app')
.controller('buildrequestController', ['$scope', 'dataService', '$stateParams', 'findBuilds', 'glBreadcrumbService', 'glTopbarContextualActionsService', 'publicFieldsFilter', BuildrequestController]);
