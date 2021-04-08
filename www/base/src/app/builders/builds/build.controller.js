/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class BuildController {
    constructor($rootScope, $scope, $location, $stateParams, $state, faviconService,
                  dataService, dataUtilsService, publicFieldsFilter,
                  glBreadcrumbService, glTopbarContextualActionsService, resultsService, $window) {
        _.mixin($scope, resultsService);

        const builderid = _.parseInt($stateParams.builder);
        const buildnumber = _.parseInt($stateParams.build);

        $scope.last_build = true;
        $scope.is_stopping = false;
        $scope.is_rebuilding = false;

        const doRebuild = function() {
            $scope.is_rebuilding = true;
            refreshContextMenu();
            const success = function(res) {
                const brid = _.values(res.result[1])[0];
                $state.go("buildrequest", {
                    buildrequest: brid,
                    redirect_to_build: true
                });
            };

            const failure = function(why) {
                $scope.is_rebuilding = false;
                $scope.error = `Cannot rebuild: ${why.error.message}`;
                refreshContextMenu();
            };

            $scope.build.control('rebuild').then(success, failure);
        };

        const doStop = function() {
            $scope.is_stopping = true;
            refreshContextMenu();

            const success = res => null;

            const failure = function(why) {
                $scope.is_stopping = false;
                $scope.error = `Cannot Stop: ${why.error.message}`;
                refreshContextMenu();
            };

            $scope.build.control('stop').then(success, failure);
        };

        var refreshContextMenu = function() {
            const actions = [];
            if (($scope.build == null)) {
                return;
            }
            faviconService.setFavIcon($scope.build);
            if ($scope.build.complete) {
                if ($scope.is_rebuilding) {
                    actions.push({
                        caption: "Rebuilding...",
                        icon: "spinner fa-spin",
                        action: doRebuild
                    });
                } else {
                    actions.push({
                        caption: "Rebuild",
                        extra_class: "btn-default",
                        action: doRebuild
                    });
                }
            } else {
                if ($scope.is_stopping) {
                    actions.push({
                        caption: "Stopping...",
                        icon: "spinner fa-spin",
                        action: doStop
                    });
                } else {
                    actions.push({
                        caption: "Stop",
                        extra_class: "btn-default",
                        action: doStop
                    });
                }
            }
            glTopbarContextualActionsService.setContextualActions(actions);
        };
        $scope.$watch('build.complete', refreshContextMenu);

        // Clear breadcrumb and contextual action buttons on destroy
        const clearGl = function () {
            glBreadcrumbService.setBreadcrumb([]);
            glTopbarContextualActionsService.setContextualActions([]);
        };
        $scope.$on('$destroy', clearGl);

        const data = dataService.open().closeOnDestroy($scope);
        data.getBuilders(builderid).onChange = function(builders) {
            let builder;
            $scope.builder = (builder = builders[0]);
            $window.document.title = $state.current.data.pageTitle({
                builder: builder['name'], build: buildnumber});

            // get the build plus the previous and next
            // note that this registers to the updates for all the builds for that builder
            // need to see how that scales
            builder.getBuilds({number__lt: buildnumber + 2, limit: 3, order: '-number'}).onChange = function(builds) {
                $scope.prevbuild = null;
                $scope.nextbuild = null;
                let build = null;
                for (let b of Array.from(builds)) {
                    if (b.number === (buildnumber - 1)) {
                        $scope.prevbuild = b;
                    }
                    if (b.number === buildnumber) {
                        $scope.build = (build = b);
                    }
                    if (b.number === (buildnumber + 1)) {
                        $scope.nextbuild = b;
                        $scope.last_build = false;
                    }
                }

                if (!build) {
                    $state.go('build', {builder: builderid, build: builds[0].number});
                    return;
                }

                const breadcrumb = [{
                        caption: "Builders",
                        sref: "builders"
                    }
                    , {
                        caption: builder.name,
                        sref: `builder({builder:${builderid}})`
                    }
                    , {
                        caption: build.number,
                        sref: `build({build:${buildnumber}})`
                    }
                ];

                glBreadcrumbService.setBreadcrumb(breadcrumb);

                var unwatch = $scope.$watch('nextbuild.number', function(n, o) {
                    if (n != null) {
                        $scope.last_build = false;
                        unwatch();
                    }
                });

                $scope.responsibles = {};
                build.getProperties().onNew = function(properties) {
                    $scope.properties = properties;
                    var owner = properties.owner[0];
                    if (properties.scheduler[0] === 'force' && owner.match(/^.+\<.+\@.+\..+\>.*$/)) {
                        var name = owner.split(new RegExp('<|>'))[0];
                        var email = owner.split(new RegExp('<|>'))[1];
                        $scope.responsibles[name] = email;
                    }
                };
                $scope.changes = build.getChanges();
                $scope.changes.onNew = change => $scope.responsibles[change.author_name] = change.author_email;

                data.getWorkers(build.workerid).onNew = worker => $scope.worker = publicFieldsFilter(worker);

                data.getBuildrequests(build.buildrequestid).onNew = function(buildrequest) {
                    $scope.buildrequest = buildrequest;
                    data.getBuildsets(buildrequest.buildsetid).onNew = function(buildset) {
                        $scope.buildset = buildset;
                        if (buildset.parent_buildid) {
                            data.getBuilds(buildset.parent_buildid).onNew = build => $scope.parent_build = build;
                        }
                    };
                };
            };
        };
    }
}


angular.module('app')
.controller('buildController', ['$rootScope', '$scope', '$location', '$stateParams', '$state', 'faviconService', 'dataService', 'dataUtilsService', 'publicFieldsFilter', 'glBreadcrumbService', 'glTopbarContextualActionsService', 'resultsService', '$window', BuildController]);
