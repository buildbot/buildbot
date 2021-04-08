/*
 * decaffeinate suggestions:
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class BuilderController {
    constructor($rootScope, $scope, dataService, $stateParams, resultsService,
        glBreadcrumbService, $state, glTopbarContextualActionsService, $q, $window) {
        // make resultsService utilities available in the template
        _.mixin($scope, resultsService);
        const data = dataService.open().closeOnDestroy($scope);
        const builderid = $stateParams.builder;
        $scope.forceschedulers = [];
        $scope.is_cancelling = false;

        // Clear breadcrumb and contextual action buttons on destroy
        const clearGl = function () {
            glBreadcrumbService.setBreadcrumb([]);
            glTopbarContextualActionsService.setContextualActions([]);
        };
        $scope.$on('$destroy', clearGl);

        data.getBuilders(builderid).onNew = function(builder) {
            $window.document.title = $state.current.data.pageTitle({
                builder: builder['name']});
            $scope.builder = builder;
            const breadcrumb = [{
                    caption: "Builders",
                    sref: "builders"
                }
                , {
                    caption: builder.name,
                    sref: `builder({builder:${builder.builderid}})`
                }
            ];

            // reinstall breadcrumb when coming back from forcesched
            $scope.$on('$stateChangeSuccess', () => glBreadcrumbService.setBreadcrumb(breadcrumb));
            glBreadcrumbService.setBreadcrumb(breadcrumb);

            const doCancel = function() {
                if ($scope.is_cancelling) {
                    return;
                }
                if (!window.confirm("Are you sure you want to cancel all builds?")) {
                    return;
                }
                $scope.is_cancelling = true;
                refreshContextMenu();

                const success = function(res) {
                    $scope.is_cancelling = false;
                    refreshContextMenu();
                };

                const failure = function(why) {
                    $scope.is_cancelling = false;
                    $scope.error = `Cannot cancel: ${why.error.message}`;
                    refreshContextMenu();
                };

                const dl = [];
                $scope.buildrequests.forEach(function(buildrequest) {
                    if (!buildrequest.claimed) {
                        dl.push(buildrequest.control('cancel'));
                    }
                });
                $scope.builds.forEach(function(build) {
                    if (!build.complete) {
                        dl.push(build.control('stop'));
                    }
                });
                $q.when(dl).then(success, failure);
            };

            var refreshContextMenu = function() {
                if ($scope.$$destroyed) {
                    return;
                }
                const actions = [
                ];
                let canStop = false;
                $scope.builds.forEach(function(build) {
                    if (!build.complete) {
                        canStop = true;
                    }
                });
                $scope.buildrequests.forEach(function(buildrequest) {
                    if (!buildrequest.claimed) {
                        canStop = true;
                    }
                });

                if (canStop) {
                    if ($scope.is_cancelling) {
                        actions.push({
                            caption: "Cancelling...",
                            icon: "spinner fa-spin",
                            action: doCancel
                        });
                    } else {
                        actions.push({
                            caption: "Cancel whole queue",
                            extra_class: "btn-danger",
                            icon: "stop",
                            action: doCancel
                        });
                    }
                }
                _.forEach($scope.forceschedulers, sch =>
                    actions.push({
                        caption: sch.button_name,
                        extra_class: "btn-primary",
                        action() {
                            return $state.go("builder.forcebuilder",
                                {scheduler:sch.name});
                        }
                    })
                );

                glTopbarContextualActionsService.setContextualActions(actions);
            };

            builder.getForceschedulers({order:'name'}).onChange = function(forceschedulers) {
                $scope.forceschedulers = forceschedulers;
                refreshContextMenu();
                // reinstall contextual actions when coming back from forcesched
                $scope.$on('$stateChangeSuccess', () => refreshContextMenu());
            };
            $scope.numbuilds = 200;
            if ($stateParams.numbuilds != null) {
                $scope.numbuilds = +$stateParams.numbuilds;
            }
            $scope.builds = builder.getBuilds({
                property: ["owners", "workername"],
                limit: $scope.numbuilds,
                order: '-number'
            });
            $scope.buildrequests = builder.getBuildrequests({claimed:false});
            $scope.buildrequests.onNew = buildrequest =>
                data.getBuildsets(buildrequest.buildsetid).onNew = buildset =>
                    buildset.getProperties().onNew = properties => buildrequest.properties = properties

            ;

            $scope.builds.onChange = function() {
                refreshContextMenu();
                if ($scope.builds.length === 0) {
                    return;
                }
                $scope.successful_builds = [];
                $scope.success_ratio = [];
                const max_started =  $scope.builds[0].started_at;
                const min_started = $scope.builds[$scope.builds.length-1].started_at;
                const threshold = (max_started - min_started)/30;  // build 30 success ratio points
                let last_started = max_started;
                let cur_success = 0;
                let num_builds = 0;
                $scope.builds.forEach(function(b) {
                    if (b.complete_at !== null) {
                        num_builds +=1;
                        if (b.results === 0) {
                            cur_success +=1;
                            b.duration = b.complete_at - b.started_at;
                            $scope.successful_builds.push(b);
                        }
                        // we walk backward? The logic is reversed to avoid another sort
                        if ((last_started - b.started_at) > threshold) {
                            $scope.success_ratio.push({date:last_started, success_ratio: (100 * cur_success) / num_builds});
                            last_started = b.started_at;
                            num_builds = 0;
                            cur_success = 0;
                        }
                    }
                });
            };
            $scope.buildrequests.onChange = refreshContextMenu;
        };
    }
}


angular.module('app')
.controller('builderController', ['$rootScope', '$scope', 'dataService', '$stateParams', 'resultsService', 'glBreadcrumbService', '$state', 'glTopbarContextualActionsService', '$q', '$window', BuilderController]);
