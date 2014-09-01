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
        $tbSorter,
        initializedCodebaseOverview = false;

    require('libs/jquery.form');

    var rtBuilders = {
        init: function () {
            $tbSorter = rtBuilders.dataTableInit($('.builders-table'));
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.builders = rtBuilders.realtimeFunctionsProcessBuilders;
            realtimePages.initRealtime(realtimeFunctions);
        },
        realtimeFunctionsProcessBuilders: function (data) {
            if (initializedCodebaseOverview === false) {
                initializedCodebaseOverview = true;

                // insert codebase and branch on the builders page
                helpers.codeBaseBranchOverview($('.dataTables_wrapper .top'), data.comparisonURL);
            }
            rtTable.table.rtfGenericTableProcess($tbSorter, data.builders);
        },
        dataTableInit: function ($tableElem) {
            var options = {};

            options.aoColumns = [
                { "mData": null, "sWidth": "20%" },
                { "mData": null, "sWidth": "10%" },
                { "mData": null, "sWidth": "15%", "sType": "number-ignore-zero" },
                { "mData": null, "sWidth": "15%", "sType": "builder-status" },
                { "mData": null, "sWidth": "5%", "bSortable": false  },
                { "mData": null, "sWidth": "15%", "bSortable": false  },
                { "mData": null, "sWidth": "5%", "sType": "natural" },
                { "mData": null, "sWidth": "5%", "bSortable": false }
            ];

            options.aoColumnDefs = [
                rtTable.cell.builderName(0, "txt-align-left"),
                rtTable.cell.buildProgress(1, false),
                rtTable.cell.buildLastRun(2),
                rtTable.cell.buildStatus(3, "latestBuild"),
                rtTable.cell.buildShortcuts(4, "latestBuild"),
                rtTable.cell.revision(5, function (data) {
                    if (data.latestBuild !== undefined) {
                        return data.latestBuild.sourceStamps;
                    }
                    return undefined;
                }, helpers.urlHasCodebases()),
                rtTable.cell.buildLength(6, function (data) {
                    if (data.latestBuild !== undefined) {
                        return data.latestBuild.times;
                    }
                    return undefined;
                }),
                {
                    "aTargets": [ 7 ],
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
