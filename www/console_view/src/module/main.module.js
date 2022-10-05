/*
 * decaffeinate suggestions:
 * DS101: Remove unnecessary use of Array.from
 * DS102: Remove unnecessary code created because of implicit returns
 * DS205: Consider reworking code to avoid use of IIFEs
 * DS207: Consider shorter variations of null checks
 * Full docs: https://github.com/decaffeinate/decaffeinate/blob/master/docs/suggestions.md
 */

import 'angular-animate';
import '@uirouter/angularjs';
import 'guanlecoja-ui';
import 'buildbot-data-js';

class ConsoleState {
    constructor($stateProvider, glMenuServiceProvider, bbSettingsServiceProvider) {

        // Name of the state
        const name = 'console';

        // Menu configuration
        glMenuServiceProvider.addGroup({
            name,
            caption: 'Console View',
            icon: 'exclamation-circle',
            order: 5
        });

        // Configuration
        const cfg = {
            group: name,
            caption: 'Console View'
        };

        // Register new state
        const state = {
            controller: `${name}Controller`,
            controllerAs: "c",
            template: require('./console.tpl.jade'),
            name,
            url: `/${name}`,
            data: cfg
        };

        $stateProvider.state(state);

        bbSettingsServiceProvider.addSettingsGroup({
            name: 'Console',
            caption: 'Console related settings',
            items: [{
                type: 'integer',
                name: 'buildLimit',
                caption: 'Number of builds to fetch',
                default_value: 200
            }
            , {
                type: 'integer',
                name: 'changeLimit',
                caption: 'Number of changes to fetch',
                default_value: 30
            }
            ]});
    }
}

class Console {
    constructor($scope, $q, $window, dataService, bbSettingsService, resultsService,
        $uibModal, $timeout) {
        this.onChange = this.onChange.bind(this);
        this._onChange = this._onChange.bind(this);
        this.matchBuildWithChange = this.matchBuildWithChange.bind(this);
        this.makeFakeChange = this.makeFakeChange.bind(this);
        this.$scope = $scope;
        this.$window = $window;
        this.$uibModal = $uibModal;
        this.$timeout = $timeout;
        angular.extend(this, resultsService);
        const settings = bbSettingsService.getSettingsGroup('Console');
        this.buildLimit = settings.buildLimit.value;
        this.changeLimit = settings.changeLimit.value;
        this.dataAccessor = dataService.open().closeOnDestroy(this.$scope);
        this._infoIsExpanded = {};
        this.$scope.all_builders = (this.all_builders = this.dataAccessor.getBuilders());
        this.$scope.builders = (this.builders = []);
        if (typeof Intl !== 'undefined' && Intl !== null) {
            const collator = new Intl.Collator(undefined, {numeric: true, sensitivity: 'base'});
            this.strcompare = collator.compare;
        } else {
            this.strcompare = function(a, b) {
                if (a < b) {
                    return -1;
                }
                if (a === b) {
                    return 0;
                }
                return 1;
            };
        }

        this.$scope.builds = (this.builds = this.dataAccessor.getBuilds({
            property: ["got_revision"],
            limit: this.buildLimit,
            order: '-started_at'
        }));
        this.changes = this.dataAccessor.getChanges({limit: this.changeLimit, order: '-changeid'});
        this.buildrequests = this.dataAccessor.getBuildrequests({limit: this.buildLimit, order: '-submitted_at'});
        this.buildsets = this.dataAccessor.getBuildsets({limit: this.buildLimit, order: '-submitted_at'});

        this.builds.onChange = this.onChange;
        this.changes.onChange = this.onChange;
        this.buildrequests.onChange = this.onChange;
        this.buildsets.onChange = this.onChange;
    }

    onChange(s) {
        // if there is no data, no need to try and build something.
        if ((this.builds.length === 0) || (this.all_builders.length === 0) || !this.changes.$resolved ||
                (this.buildsets.length === 0) || (this.buildrequests === 0)) {
            return;
        }
        if ((this.onchange_debounce == null)) {
            this.onchange_debounce = this.$timeout(this._onChange, 100);
        }
    }

    _onChange() {
        let build, change;
        this.onchange_debounce = undefined;
        // we only display builders who actually have builds
        for (build of Array.from(this.builds)) {
            this.all_builders.get(build.builderid).hasBuild = true;
        }

        this.sortBuildersByTags(this.all_builders);

        if (this.changesBySSID == null) { this.changesBySSID = {}; }
        if (this.changesByRevision == null) { this.changesByRevision = {}; }
        for (change of Array.from(this.changes)) {
            this.changesBySSID[change.sourcestamp.ssid] = change;
            this.changesByRevision[change.revision] = change;
            this.populateChange(change);
        }


        for (build of Array.from(this.builds)) {
            this.matchBuildWithChange(build);
        }

        this.filtered_changes = [];

        for (let ssid in this.changesBySSID) {
            change = this.changesBySSID[ssid];
            if (change.comments) {
                change.subject = change.comments.split("\n")[0];
            }
            for (let builder of Array.from(change.builders)) {
                if (builder.builds.length > 0) {
                    this.filtered_changes.push(change);
                    break;
                }
            }
        }
    }
    /*
     * Sort builders by tags
     * Buildbot eight has the category option, but it was only limited to one category per builder,
     * which make it easy to sort by category
     * Here, we have multiple tags per builder, we need to try to group builders with same tags together
     * The algorithm is rather twisted. It is a first try at the concept of grouping builders by tags..
     */

    sortBuildersByTags(all_builders) {
        // first we only want builders with builds
        let tag;
        const builders_with_builds = [];
        let builderids_with_builds = "";
        for (let builder of Array.from(all_builders)) {
            if (builder.hasBuild) {
                builders_with_builds.push(builder);
                builderids_with_builds += `.${builder.builderid}`;
            }
        }

        if (builderids_with_builds === this.last_builderids_with_builds) {
            // don't recalculate if it hasn't changed!
            return;
        }
        // we call recursive function, which finds non-overlapping groups
        let tag_line = this._sortBuildersByTags(builders_with_builds);
        // we get a tree of builders grouped by tags
        // we now need to flatten the tree, in order to build several lines of tags
        // (each line is representing a depth in the tag tree)
        // we walk the tree left to right and build the list of builders in the tree order, and the tag_lines
        // in the tree, there are groups of remaining builders, which could not be grouped together,
        // those have the empty tag ''
        const tag_lines = [];

        let sorted_builders = [];
        const set_tag_line = function(depth, tag, colspan) {
            // we build the tag lines by using a sparse array
            let _tag_line = tag_lines[depth];
            if ((_tag_line == null)) {
                // initialize the sparse array
                _tag_line = (tag_lines[depth] = []);
            } else {
                // if we were already initialized, look at the last tag if this is the same
                // we merge the two entries
                const last_tag = _tag_line[_tag_line.length - 1];
                if (last_tag.tag === tag) {
                    last_tag.colspan += colspan;
                    return;
                }
            }
            return _tag_line.push({tag, colspan});
        };
        const self = this;
        // recursive tree walking
        var walk_tree = function(tag, depth) {
            set_tag_line(depth, tag.tag, tag.builders.length);
            if ((tag.tag_line == null) || (tag.tag_line.length === 0)) {
                // this is the leaf of the tree, sort by buildername, and add them to the
                // list of sorted builders
                tag.builders.sort((a, b) => self.strcompare(a.name, b.name));
                sorted_builders = sorted_builders.concat(tag.builders);
                for (let i = 1; i <= 100; i++) {  // set the remaining depth of the tree to the same colspan
                                   // (we hardcode the maximum depth for now :/ )
                    set_tag_line(depth + i, '', tag.builders.length);
                }
                return;
            }
            return Array.from(tag.tag_line).map((_tag) =>
                walk_tree(_tag, depth + 1));
        };

        for (tag of Array.from(tag_line)) {
            walk_tree(tag, 0);
        }

        this.builders = sorted_builders;
        this.tag_lines = [];
        // make a new array to avoid it to be sparse, and to remove lines filled with null tags
        for (tag_line of Array.from(tag_lines)) {
            if (!((tag_line.length === 1) && (tag_line[0].tag === ""))) {
                this.tag_lines.push(tag_line);
            }
        }
        return this.last_builderids_with_builds = builderids_with_builds;
    }
    /*
     * recursive function which sorts the builders by tags
     * call recursively with groups of builders smaller and smaller
     */
    _sortBuildersByTags(all_builders) {

        // first find out how many builders there is by tags in that group
        let builder, builders, tag;
        const builders_by_tags = {};
        for (builder of Array.from(all_builders)) {
            if (builder.tags != null) {
                for (tag of Array.from(builder.tags)) {
                    if ((builders_by_tags[tag] == null)) {
                        builders_by_tags[tag] = [];
                    }
                    builders_by_tags[tag].push(builder);
                }
            }
        }
        const tags = [];
        for (tag in builders_by_tags) {
            // we don't want the tags that are on all the builders
            builders = builders_by_tags[tag];
            if (builders.length < all_builders.length) {
                tags.push({tag, builders});
            }
        }

        // sort the tags to first look at tags with the larger number of builders
        // @FIXME maybe this is not the best method to find the best groups
        tags.sort((a, b) => b.builders.length - a.builders.length);

        const tag_line = [];
        const chosen_builderids = {};
        // pick the tags one by one, by making sure we make non-overalaping groups
        for (tag of Array.from(tags)) {
            let excluded = false;
            for (builder of Array.from(tag.builders)) {
                if (chosen_builderids.hasOwnProperty(builder.builderid)) {
                    excluded = true;
                    break;
                }
            }
            if (!excluded) {
                for (builder of Array.from(tag.builders)) {
                    chosen_builderids[builder.builderid] = tag.tag;
                }
                tag_line.push(tag);
            }
        }

        // some builders do not have tags, we put them in another group
        const remaining_builders = [];
        for (builder of Array.from(all_builders)) {
            if (!chosen_builderids.hasOwnProperty(builder.builderid)) {
                remaining_builders.push(builder);
            }
        }

        if (remaining_builders.length) {
            tag_line.push({tag: "", builders: remaining_builders});
        }

        // if there is more than one tag in this line, we need to recurse
        if (tag_line.length > 1) {
            for (tag of Array.from(tag_line)) {
                tag.tag_line = this._sortBuildersByTags(tag.builders);
            }
        }
        return tag_line;
    }

    /*
     * fill a change with a list of builders
     */
    populateChange(change) {
        change.builders = [];
        change.buildersById = {};
        for (let builder of Array.from(this.builders)) {
            builder = {builderid: builder.builderid, name: builder.name, builds: []};
            change.builders.push(builder);
            change.buildersById[builder.builderid] = builder;
        }
    }
    /*
     * Match builds with a change
     */
    matchBuildWithChange(build) {
        let change, revision;
        const buildrequest = this.buildrequests.get(build.buildrequestid);
        if ((buildrequest == null)) {
            return;
        }
        const buildset = this.buildsets.get(buildrequest.buildsetid);
        if ((buildset == null)) {
            return;
        }
        if  ((buildset != null) && (buildset.sourcestamps != null)) {
            for (let sourcestamp of Array.from(buildset.sourcestamps)) {
                change = this.changesBySSID[sourcestamp.ssid];
                if (change != null) {
                    break;
                }
            }
        }

        if ((change == null) && ((build.properties != null ? build.properties.got_revision : undefined) != null)) {
            const rev = build.properties.got_revision[0];
            // got_revision can be per codebase or just the revision string
            if (typeof(rev) === "string") {
                change = this.changesByRevision[rev];
                if ((change == null)) {
                    change = this.makeFakeChange("", rev, build.started_at);
                }
            } else {
                let codebase;
                for (codebase in rev) {
                    revision = rev[codebase];
                    change = this.changesByRevision[revision];
                    if (change != null) {
                        break;
                    }
                }

                if ((change == null)) {
                    revision = rev === {} ? "" : rev[Object.keys(rev)[0]];
                    change = this.makeFakeChange(codebase, revision, build.started_at);
                }
            }
        }

        if ((change == null)) {
            revision = `unknown revision ${build.builderid}-${build.buildid}`;
            change = this.makeFakeChange("unknown codebase", revision, build.started_at);
        }

        return change.buildersById[build.builderid].builds.push(build);
    }

    makeFakeChange(codebase, revision, when_timestamp) {
        let change = this.changesBySSID[revision];
        if ((change == null)) {
            change = {
                codebase,
                revision,
                changeid: revision,
                when_timestamp,
                author: `unknown author for ${revision}`,
                comments: revision + "\n\nFake comment for revision: No change for this revision, please setup a changesource in Buildbot"
            };
            this.changesBySSID[revision] = change;
            this.populateChange(change);
        }
        return change;
    }
    /*
     * Open all change row information
     */
    openAll() {
        return Array.from(this.filtered_changes).map((change) =>
            (change.show_details = true));
    }

    /*
     * Close all change row information
     */
    closeAll() {
        return Array.from(this.filtered_changes).map((change) =>
            (change.show_details = false));
    }

    /*
     * Calculate row header (aka first column) width
     * depending if we display commit comment, we reserve more space
     */
    getRowHeaderWidth() {
        if (this.hasExpanded()) {
            return 400;  // magic value enough to hold 78 characters lines
        } else {
            return 200;
        }
    }
    /*
     * Calculate col header (aka first row) height
     * It depends on the length of the longest builder
     */
    getColHeaderHeight() {
        let max_buildername = 0;
        for (let builder of Array.from(this.builders)) {
            max_buildername = Math.max(builder.name.length, max_buildername);
        }
        return Math.max(100, max_buildername * 3);
    }

    /*
     *
     * Determine if we use a 100% width table or if we allow horizontal scrollbar
     * depending on number of builders, and size of window, we need a fixed column size or a 100% width table
     *
     */
    isBigTable() {
        const padding = this.getRowHeaderWidth();
        if (((this.$window.innerWidth - padding) / this.builders.length) < 40) {
            return true;
        }
        return false;
    }
    /*
     *
     * do we have at least one change expanded?
     *
     */
    hasExpanded() {
        for (let change of Array.from(this.changes)) {
            if (this.infoIsExpanded(change)) {
                return true;
            }
        }
        return false;
    }

    /*
     *
     * display build details
     *
     */
    selectBuild(build) {
        let modal;
        return modal = this.$uibModal.open({
            template: require('./view/modal/modal.tpl.jade'),
            controller: 'consoleModalController as modal',
            windowClass: 'modal-big',
            resolve: {
                selectedBuild() { return build; }
            }
        });
    }

    /*
     *
     * toggle display of additional info for that change
     *
     */
    toggleInfo(change) {
        return change.show_details = !change.show_details;
    }
    infoIsExpanded(change) {
        return change.show_details;
    }
}


angular.module('console_view', [
    'ui.router', 'ui.bootstrap', 'ngAnimate', 'guanlecoja.ui', 'bbData'])
.config(['$stateProvider', 'glMenuServiceProvider', 'bbSettingsServiceProvider', ConsoleState])
.controller('consoleController', ['$scope', '$q', '$window', 'dataService', 'bbSettingsService', 'resultsService', '$uibModal', '$timeout', Console]);

require('./view/modal/modal.controller.js');
