/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */
class Builders {
    constructor($scope, $log, dataService, resultsService, bbSettingsService, $stateParams,
        $location, dataGrouperService, $rootScope, $filter,
        glBreadcrumbService, glTopbarContextualActionsService) {
        const breadcrumb = [{
                caption: "Builders",
                sref: "builders"
            }
        ];
        const setupGl = function () {
            glBreadcrumbService.setBreadcrumb(breadcrumb);
            glTopbarContextualActionsService.setContextualActions([]);
        };
        $scope.$on('$stateChangeSuccess', setupGl);
        setupGl();

        // Clear breadcrumb and contextual action buttons on destroy
        const clearGl = function () {
            glBreadcrumbService.setBreadcrumb([]);
            glTopbarContextualActionsService.setContextualActions([]);
        };
        $scope.$on('$destroy', clearGl);

        // make resultsService utilities available in the template
        _.mixin($scope, resultsService);
        $scope.connected2class = function(worker) {
            if (worker.connected_to.length > 0) {
                return "worker_CONNECTED";
            } else {
                return "worker_DISCONNECTED";
            }
        };
        $scope.hasActiveMaster = function(builder) {
            let active = false;
            if ((builder.masterids == null)) {
                return false;
            }
            for (let mid of Array.from(builder.masterids)) {
                const m = $scope.masters.get(mid);
                if ((m != null) && m.active) {
                    active = true;
                }
            }
            if (builder.tags.includes('_virtual_')) {
                active = true;
            }
            return active;
        };
        $scope.settings = bbSettingsService.getSettingsGroup("Builders");
        $scope.$watch('settings', () => { bbSettingsService.save(); }, true);
        const buildFetchLimit = $scope.settings.buildFetchLimit.value;

        $scope.page_size = $scope.settings.page_size.value;
        $scope.currentPage = 1;

        const updateTagsFilterFromLocation = function() {
            $scope.tags_filter = $location.search()["tags"];
            if ($scope.tags_filter == null) { $scope.tags_filter = []; }
            if (!angular.isArray($scope.tags_filter)) {
                return $scope.tags_filter = [$scope.tags_filter];
            }
        };

        updateTagsFilterFromLocation();

        $scope.$watch("tags_filter", function(tags, old) {
            if (old != null) {
                $location.search("tags", tags);
            }
        }
        , true);

        $rootScope.$on('$locationChangeSuccess', updateTagsFilterFromLocation);

        $scope.isBuilderFiltered = function(builder, index) {

            // filter out inactive builders
            let tag;
            if (!$scope.settings.show_old_builders.value && !$scope.hasActiveMaster(builder)) {
                return false;
            }

            const pluses = _.filter($scope.tags_filter, tag => tag.indexOf("+") === 0);
            const minuses = _.filter($scope.tags_filter, tag => tag.indexOf("-") === 0);

            // First enforce that we have no tag marked '-'
            for (tag of Array.from(minuses)) {
                if (builder.tags.indexOf(tag.slice(1)) >= 0) {
                    return false;
                }
            }

            // if only minuses or no filter
            if ($scope.tags_filter.length === minuses.length) {
                return true;
            }

            // Then enforce that we have all the tags marked '+'
            for (tag of Array.from(pluses)) {
                if (builder.tags.indexOf(tag.slice(1)) < 0) {
                    return false;
                }
            }

            // Then enforce that we have at least one of the tag (marked '+' or not)
            for (tag of Array.from($scope.tags_filter)) {
                if (tag.indexOf("+") === 0) {
                    tag = tag.slice(1);
                }
                if (builder.tags.indexOf(tag) >= 0) {
                    return true;
                }
            }
            return false;
        };

        $scope.isTagFiltered = tag =>
            ($scope.tags_filter.length === 0) || ($scope.tags_filter.indexOf(tag) >= 0) ||
                ($scope.tags_filter.indexOf(`+${tag}`) >= 0) || ($scope.tags_filter.indexOf(`-${tag}`) >= 0)
        ;

        $scope.toggleTag = function(tag) {
            if (tag.indexOf('+') === 0) {
                tag = tag.slice(1);
            }
            if (tag.indexOf('-') === 0) {
                tag = tag.slice(1);
            }
            const i = $scope.tags_filter.indexOf(tag);
            const iplus = $scope.tags_filter.indexOf(`+${tag}`);
            const iminus = $scope.tags_filter.indexOf(`-${tag}`);
            if ((i < 0) && (iplus < 0) && (iminus < 0)) {
                return $scope.tags_filter.push(`+${tag}`);
            } else if (iplus >= 0) {
                $scope.tags_filter.splice(iplus, 1);
                return $scope.tags_filter.push(`-${tag}`);
            } else if (iminus >= 0) {
                $scope.tags_filter.splice(iminus, 1);
                return $scope.tags_filter.push(tag);
            } else {
                return $scope.tags_filter.splice(i, 1);
            }
        };

        const data = dataService.open().closeOnDestroy($scope);

        // as there is usually lots of builders, its better to get the overall
        // list of workers, masters, and builds and then associate by builder
        $scope.builders = data.getBuilders();
        $scope.masters = data.getMasters();
        const workers = data.getWorkers();
        let builds = null;

        const requeryBuilds = function() {
            $scope.builders.forEach(builder => builder.builds = []);

            const filteredBuilds = $filter('filter')($scope.builders, $scope.isBuilderFiltered) || [];
            let builderIds = filteredBuilds.map(builder => builder.builderid);
            if (builderIds.length === $scope.builders.length) { builderIds = []; }

            builds = data.getBuilds({limit: buildFetchLimit, order: '-started_at', builderid__eq: builderIds});
            dataGrouperService.groupBy($scope.builders, workers, 'builderid', 'workers', 'configured_on');
            dataGrouperService.groupBy($scope.builders, builds, 'builderid', 'builds');
        };

        if ($scope.tags_filter.length === 0) {
            requeryBuilds();
        } else {
            $scope.$watch("builders.$resolved", function(resolved) {
                if (resolved) {
                    requeryBuilds();
                }
            });
        }

        $scope.searchQuery = '';

        $scope.$watch("tags_filter", function() {
            if (builds && $scope.builders.$resolved) {
                builds.close();
                requeryBuilds();
            }
        }
        , true);
    }
}

angular.module('app')
.controller('buildersController', ['$scope', '$log', 'dataService', 'resultsService', 'bbSettingsService', '$stateParams', '$location', 'dataGrouperService', '$rootScope', '$filter', 'glBreadcrumbService', 'glTopbarContextualActionsService', Builders]);
