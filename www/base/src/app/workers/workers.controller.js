/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Workers {
    constructor($scope, dataService, bbSettingsService, resultsService, dataGrouperService, $stateParams, $state, glTopbarContextualActionsService, glBreadcrumbService) {
        let builds;
        $scope.capitalize = _.capitalize;
        _.mixin($scope, resultsService);


        $scope.getUniqueBuilders = function(worker) {
            const builders = {};
            const masters = {};
            for (let master of Array.from(worker.connected_to)) {
                masters[master.masterid] = true;
            }
            for (let buildermaster of Array.from(worker.configured_on)) {
                if ((worker.connected_to.length === 0) || masters.hasOwnProperty(buildermaster.masterid)) {
                    const builder = $scope.builders.get(buildermaster.builderid);
                    if (builder != null) {
                        builders[buildermaster.builderid] = builder;
                    }
                }
            }
            return _.values(builders);
        };
        $scope.maybeHideWorker = function(worker) {
            if ($stateParams.worker != null) {
                return worker.workerid !== +$stateParams.worker;
            }
            if ($scope.settings.show_old_workers.value) {
                return 0;
            }
            return worker.configured_on.length === 0;
        };

        const data = dataService.open().closeOnDestroy($scope);

        // Clear breadcrumb and contextual action buttons on destroy
        const clearGl = function() {
            glTopbarContextualActionsService.setContextualActions([]);
            glBreadcrumbService.setBreadcrumb([]);
        };
        $scope.$on('$destroy', clearGl);

        $scope.builders = data.getBuilders();
        $scope.masters = data.getMasters();
        $scope.workers = data.getWorkers();
        $scope.workers.onChange =  function(workers) {
            let worker;
            const breadcrumb = [{
                    caption: "Workers",
                    sref: "workers"
                }
            ];
            const actions = [];
            if ($stateParams.worker != null) {
                $scope.worker = (worker = workers.get(+$stateParams.worker));

                breadcrumb.push({
                    caption: worker.name,
                    sref: `worker({worker:${worker.workerid}})`
                });

                actions.push({
                    caption: "Actions...",
                    extra_class: "btn-default",
                    action() {
                        return $state.go("worker.actions");
                    }
                });
            } else {
                actions.push({
                    caption: "Actions...",
                    extra_class: "btn-default",
                    action() {
                        return $state.go("workers.actions");
                    }
                });
            }
            // reinstall breadcrumb when coming back from forcesched
            const setupGl = function() {
                glTopbarContextualActionsService.setContextualActions(actions);
                glBreadcrumbService.setBreadcrumb(breadcrumb);
            };
            $scope.$on('$stateChangeSuccess', setupGl);
            setupGl();

            $scope.worker_infos = [];
            for (worker of Array.from(workers)) {
                worker.num_connections = worker.connected_to.length;
                for (let k in worker.workerinfo) {
                    // we only count workerinfo that is at least defined in one worker
                    const v = worker.workerinfo[k];
                    if ((v != null) && (v !== "") && ($scope.worker_infos.indexOf(k) < 0)) {
                        $scope.worker_infos.push(k);
                    }
                }
            }
            $scope.worker_infos.sort();
        };

        const byNumber = (a, b) => a.number - b.number;
        $scope.numbuilds = 200;
        if ($stateParams.numbuilds != null) {
            $scope.numbuilds = +$stateParams.numbuilds;
        }
        if ($stateParams.worker != null) {
            $scope.builds = (builds = data.getBuilds({
                limit: $scope.numbuilds, workerid: +$stateParams.worker, order: '-started_at', property: ["owners", "workername"]}));
        } else {
            builds = data.getBuilds({limit: $scope.numbuilds, order: '-started_at', property: ["owners", "workername"]});
        }
        dataGrouperService.groupBy($scope.workers, builds, 'workerid', 'builds');
        $scope.settings = bbSettingsService.getSettingsGroup("Workers");
        $scope.$watch('settings', () => { bbSettingsService.save(); }, true);
    }
}


angular.module('app')
.controller('workersController', ['$scope', 'dataService', 'bbSettingsService', 'resultsService', 'dataGrouperService', '$stateParams', '$state', 'glTopbarContextualActionsService', 'glBreadcrumbService', Workers]);
