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
        savedTags = [],
        $tagsSelect,
        NO_TAG = "No Tag",
        extra_tags = [NO_TAG];

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
            return true;
        },
        loadState: function loadState(oSettings, oData) {
            if (oData.tags !== undefined) {
                savedTags = oData.tags;
            }
            return true;
        },
        findAllTags: function findAllTags(data) {
            tags.clear();
            $.each(data, function eachBuilder(i, builder) {
                tags = tags.add(builder.tags);
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
                    builderTags = data[col];

                if (selectedTags.length === 0) {
                    return true;
                }

                if (builderTags.length === 0) {
                    return $.inArray("No Tag", selectedTags) > -1;
                }

                var result = false;
                $.each(builderTags, function (i, tag) {
                    if ($.inArray(tag, selectedTags) > -1) {
                        result = true;
                        return false;
                    }
                });
                return result;
            };
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
                rtTable.cell.builderTags(0),
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
