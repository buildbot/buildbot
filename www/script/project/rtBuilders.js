/*global define, Handlebars*/
define(function (require) {
    "use strict";

    var $ = require('jquery'),
        realtimePages = require('realtimePages'),
        helpers = require('helpers'),
        dt = require('project/datatables-extend'),
        rtTable = require('rtGenericTable'),
        popup = require('ui.popup'),
        hb = require('project/handlebars-extend'),
        MiniSet = require('project/sets'),
        $tbSorter,
        initializedCodebaseOverview = false,
        latestRevDict = {},
        tags = new MiniSet(),
        branch_tags = new MiniSet(),// All of the tags that only contain a branch i.e 4.6, Trunk
        tagAsBranchRegex = /^([0-9].[0-9]|trunk)$/i, // Regex for finding tags that are named the same as branches
        savedTags = [],
        $tagsSelect,
        NO_TAG = "No Tag",
        UNSTABLE_TAG = "Unstable",
        extra_tags = [NO_TAG],
        MAIN_REPO = "unity_branch",
        hideUnstable = false;

    require('libs/jquery.form');

    var rtBuilders = {
        init: function () {
            $.fn.dataTableExt.afnFiltering.push(rtBuilders.filterByTags(0));
            $tbSorter = rtBuilders.dataTableInit($('.builders-table'));
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.builders = rtBuilders.realtimeFunctionsProcessBuilders;
            realtimePages.initRealtime(realtimeFunctions);
        },
        realtimeFunctionsProcessBuilders: function (data) {
            if (initializedCodebaseOverview === false) {
                initializedCodebaseOverview = true;

                // insert codebase and branch on the builders page
                rtBuilders.findAllTags(data.builders);
                helpers.tableHeader($('.dataTables_wrapper .top'), data.comparisonURL, tags.keys().sort());

                var $unstableButton = $("#btn-unstable");
                $unstableButton.click(function() {
                    hideUnstable = !hideUnstable;
                    rtBuilders.updateUnstableButton();
                    $tbSorter.fnDraw();
                });
                rtBuilders.updateUnstableButton();

                $tagsSelect = $("#tags-select");
                $tagsSelect.on("change", function change() {
                    $tbSorter.fnDraw();
                });

                if (savedTags !== undefined && savedTags.length) {
                    var str = "";
                    $.each(savedTags, function (i, tag) {
                        str += tag + ",";
                    });
                    $tagsSelect.val(str);
                    rtBuilders.setupTagsSelector();
                } else {
                    rtBuilders.setupTagsSelector();
                }
            }
            latestRevDict = data.latestRevisions;
            rtTable.table.rtfGenericTableProcess($tbSorter, data.builders);

            //Setup tooltips
            helpers.tooltip($("[data-title]"));
        },
        setupTagsSelector: function setupTagsSelector() {
            $tagsSelect.select2({
                multiple: true,
                data: rtBuilders.parseTags()
            });
        },
        parseTags: function parseTags() {
            var results = [];
            $.each(tags.keys(), function (i, tag) {
                results.push({id: tag, text: tag})
            });
            return {results: results};
        },
        saveState: function saveState(oSettings, oData) {
            oData.tags = rtBuilders.getSelectedTags();
            oData.hide_unstable = hideUnstable;
            return true;
        },
        loadState: function loadState(oSettings, oData) {
            if (oData.tags !== undefined) {
                savedTags = oData.tags;
                hideUnstable = oData.hide_unstable;
                rtBuilders.updateUnstableButton();
            }
            return true;
        },
        findAllTags: function findAllTags(data) {
            var branch_type = rtBuilders.getBranchType();

            tags.clear();
            $.each(data, function eachBuilder(i, builder) {
                tags = tags.add(rtBuilders.formatTags(builder.tags, branch_type));

                $.each(builder.tags, function eachBuilderTag(i, tag) {
                    // If we found a branch tag then add it
                    if (tagAsBranchRegex.exec(tag)) {
                        branch_tags.add(tag.toLowerCase());
                    }
                });
            });

            tags.add(extra_tags)
        },
        getSelectedTags: function getSelectedTags() {
            var selectedTags = [];
            if ($tagsSelect !== undefined) {
                $.each($tagsSelect.val().split(","), function (i, tag) {
                    if (tag.length) {
                        selectedTags.push(tag.trim());
                    }
                });
            }

            return selectedTags;
        },
        filterByTags: function filterByTags(col) {
            return function (settings, data) {
                var selectedTags = rtBuilders.getSelectedTags(),
                    builderTags = data[col],
                    branch_type = rtBuilders.getBranchType(),
                    hasBranch = function (b) {
                        return b.toLowerCase() === branch_type.toLowerCase();
                    };

                if (hideUnstable === true && $.inArray(UNSTABLE_TAG, builderTags) > -1) {
                    return false;
                }

                var filteredTags = rtBuilders.filterTags(builderTags, branch_type);
                if (selectedTags.length == 0 && (builderTags.length > 0 && filteredTags.length === 0 || builderTags.length !== filteredTags.length)) {
                    return builderTags.some(hasBranch);
                }

                if (selectedTags.length === 0) {
                    return true;
                }

                if (builderTags.length === 0) {
                    return $.inArray(NO_TAG, selectedTags) > -1;
                }

                var result = true;
                if ($.inArray(NO_TAG, selectedTags) > -1) {
                    selectedTags.push(branch_type);
                }
                $.each(selectedTags, function eachSelectedTag(i, tag) {
                    if (tag === NO_TAG) {
                        if (filteredTags.length == 0 && builderTags.some(hasBranch)) {
                            // Exit early we have found a builder with the branch as a tag
                            return false;
                        }
                    } else if ($.inArray(tag, filteredTags) === -1) {
                        result = false;
                        return false;
                    }
                });
                return result;
            };
        },
        getBranchType: function getBranchType() {
            var branches = helpers.codebasesFromURL({}),
                regex = [
                    /^(trunk)/,                 // Trunk
                    /^([0-9].[0-9])\//,         // 5.0/
                    /^release\/([0-9].[0-9])/   // release/4.6
                ],
                branch_type = undefined;

            $.each(regex, function eachRegex(i, r) {
                $.each(branches, function eachBranch(repo, b) {
                    b = decodeURIComponent(b);
                    var matches = r.exec(b);
                    if (matches !== null && matches.length > 0) {
                        branch_type = matches[1];
                        return false;
                    }
                });
            });

            // If the branch is not found as one of the branch tags i.e 4.5, then default to trunk
            // or if the main repo is being used on this page then also default to trunk
            if ((branch_type !== undefined && $.inArray(branch_type, branch_tags.keys()) === -1) ||
                (branch_type === undefined && $.inArray(MAIN_REPO, Object.keys(branches)) > -1 &&
                branches[MAIN_REPO] !== undefined && branches[MAIN_REPO].length)) {
                return "trunk"; // Default to trunk
            }

            return branch_type;
        },
        filterTags: function filterTags(tags) {
            var branch_type = rtBuilders.getBranchType();

            var filtered_tags = tags.filter(function (tag) {
                return rtBuilders.tagVisibleForBranch(tag, branch_type)
            });

            return rtBuilders.formatTags(filtered_tags, branch_type);

        },
        formatTags: function formatTags(tags, branch_type) {
            var formatTag = function (tag) {
                if (tag.indexOf("-") > -1) {
                    return tag.replace(new RegExp(branch_type + "-", "gi"), "");
                }

                return tag;
            };

            if (Array.isArray(tags)) {
                var output = [];
                $.each(tags, function eachTag(i, tag) {
                    var formatted_tag = formatTag(tag);
                    if (rtBuilders.tagVisibleForBranch(tag, branch_type) &&
                        $.inArray(formatted_tag, output) === -1) {
                        output.push(formatTag(tag));
                    }
                });
                return output;
            }

            return formatTag(tags);
        },
        tagVisibleForBranch: function tagVisibleForBranch(tag, branch_type) {
            if (branch_type === undefined) {
                return true;
            }
            if (tag.indexOf("-") > -1) {
                return tag.toLowerCase().indexOf(branch_type.toLowerCase()) > -1;
            }
            return !tagAsBranchRegex.exec(tag);
        },
        setHideUnstable: function setHideUnstable(hidden) {
          hideUnstable = hidden;
        },
        isUnstableHidden: function isUnstableHidden() {
            return hideUnstable;
        },
        updateUnstableButton: function() {
            var $unstableButton = $("#btn-unstable");
            $unstableButton.removeClass("btn-danger btn-success");
            if (hideUnstable) {
                $unstableButton.addClass("btn-success").text("");
            } else {
                $unstableButton.addClass("btn-danger").text("");
            }
        },
        dataTableInit: function ($tableElem) {
            var options = {};

            options.iFilterCol = 1;
            options.fnStateSaveParams = rtBuilders.saveState;
            options.fnStateLoadParams = rtBuilders.loadState;

            options.aoColumns = [
                {"mData": null, "sWidth": "7%", "sType": "string-ignore-empty"},
                {"mData": null, "sWidth": "13%", "sType": "builder-name"},
                {"mData": null, "sWidth": "10%"},
                {"mData": null, "sWidth": "15%", "sType": "number-ignore-zero"},
                {"mData": null, "sWidth": "15%", "sType": "builder-status"},
                {"mData": null, "sWidth": "5%", "bSortable": false},
                {"mData": null, "sWidth": "15%", "bSortable": false},
                {"mData": null, "sWidth": "5%", "sType": "natural"},
                {"mData": null, "sWidth": "5%", "bSortable": false}
            ];

            options.aaSorting = [
                [1, "asc"]
            ];

            options.aoColumnDefs = [
                rtTable.cell.builderTags(0, rtBuilders.filterTags),
                rtTable.cell.builderName(1, "txt-align-left"),
                rtTable.cell.buildProgress(2, false),
                rtTable.cell.buildLastRun(3),
                rtTable.cell.buildStatus(4, "latestBuild"),
                rtTable.cell.buildShortcuts(5, "latestBuild"),
                rtTable.cell.revision(6, function (data) {
                    if (data.latestBuild !== undefined) {
                        return data.latestBuild.sourceStamps;
                    }
                    return undefined;
                }, helpers.urlHasCodebases(), function getLatestRevDict() {
                    return latestRevDict;
                }),
                rtTable.cell.buildLength(7, function (data) {
                    if (data.latestBuild !== undefined) {
                        return data.latestBuild.times;
                    }
                    return undefined;
                }),
                {
                    "aTargets": [8],
                    "mRender": function (data, full, type) {
                        return hb.builders({customBuild: true, url: type.url, builderName: type.name});
                    },
                    "fnCreatedCell": function (nTd) {
                        var $nTd = $(nTd);
                        var $instantBuildBtn = $nTd.find(".instant-build");
                        popup.initRunBuild($nTd.find(".custom-build"), $instantBuildBtn);
                    }
                }

            ];

            return dt.initTable($tableElem, options);
        },
        noTag: NO_TAG
    };

    return rtBuilders;
});
