/*global define, Handlebars*/
define(function (require) {
    "use strict";

    var $ = require('jquery'),
        realtimePages = require('realtimePages'),
        helpers = require('helpers'),
        dt = require('datatables-extend'),
        rtTable = require('rtGenericTable'),
        popup = require('ui.popup'),
        hb = require('project/handlebars-extend'),
        MiniSet = require('project/sets'),
        $tbSorter,
        initializedCodebaseOverview = false,
        latestRevDict = {},
        tags = new MiniSet(),
        savedTags = [];

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
                helpers.codeBaseBranchOverview($('.dataTables_wrapper .top'), data.comparisonURL, tags.keys().sort());

                $(".tags :checkbox").click(function click() {
                    $tbSorter.fnDraw();
                });

                if (savedTags !== undefined && savedTags.length) {
                    $.each(savedTags, function (i, tag) {
                        $("#tag-" + tag).prop('checked', true);
                    });
                }
            }
            latestRevDict = data.latestRevisions;
            rtTable.table.rtfGenericTableProcess($tbSorter, data.builders);
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
        },
        getSelectedTags: function getSelectedTags() {
            var selectedTags = [];
            $.each($(".tags :checkbox"), function (i, input) {
                if ($(input).is(":checked")) {
                    selectedTags.push($(input).attr("data-tag"));
                }
            });

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
                    if ($.inArray("None", selectedTags) > -1) {
                        return true;
                    }

                    return false;
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
                { "mData": null, "sWidth": "7%", "sType": "string-ignore-empty" },
                { "mData": null, "sWidth": "13%", "sType": "builder-name" },
                { "mData": null, "sWidth": "10%" },
                { "mData": null, "sWidth": "15%", "sType": "number-ignore-zero" },
                { "mData": null, "sWidth": "15%", "sType": "builder-status" },
                { "mData": null, "sWidth": "5%", "bSortable": false  },
                { "mData": null, "sWidth": "15%", "bSortable": false  },
                { "mData": null, "sWidth": "5%", "sType": "natural" },
                { "mData": null, "sWidth": "5%", "bSortable": false }
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
        }
    };

    return rtBuilders;
});
