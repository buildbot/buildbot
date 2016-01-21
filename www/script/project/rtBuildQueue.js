/*global define*/
define(function (require) {
    "use strict";

    var $ = require('jquery'),
        realtimePages = require('realtimePages'),
        helpers = require('helpers'),
        dt = require('project/datatables-extend'),
        hb = require('project/handlebars-extend'),
        timeElements = require('timeElements'),
        popup = require('ui.popup'),
        rtTable = require('rtGenericTable'),
        moment = require('moment'),
        hbBuildQueue = hb.buildQueue,
        $tbSorter,
        rtBuildQueue;

    rtBuildQueue = {
        init: function () {
            $tbSorter = rtBuildQueue.dataTableInit();

            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.queue = rtBuildQueue.processBuildQueue;
            realtimePages.initRealtime(realtimeFunctions);
            // check all in tables and remove builds
            helpers.selectBuildsAction($tbSorter, false, '/buildqueue/_selected/cancelselected', 'cancelselected=',
                rtTable.table.rtfGenericTableProcess);

        },
        processBuildQueue: function (data) {
            rtTable.table.rtfGenericTableProcess($tbSorter, data);
        },
        dataTableInit: function () {
            var options = {};

            options.aoColumns = [
                { "mData": null, "sWidth": "4%", bSortable: false },
                { "mData": null, "sWidth": "10%", bSortable: false },
                { "mData": "builderFriendlyName", "sWidth": "28%" },
                { "mData": "sources", "sWidth": "10%" },
                { "mData": "reason", "sWidth": "30%" },
                { "mData": "slaves", "sWidth": "10%" },
                { "mData": "brid", "sWidth": "6%" }
            ];

            options.aoColumnDefs = [
                {
                    "aTargets": [0],
                    "sClass": "txt-align-center",
                    "mRender": function (data, type, full) {
                        // If the build result is not resume then we are in the normal queue and not the
                        // resume queue
                        return helpers.getPendingIcons(hb, data);
                    }
                },
                {
                    "aTargets": [1],
                    "sClass": "txt-align-center",
                    "mRender": function (data, type, full) {
                        return helpers.getPriorityData(data, full);
                    }
                },
                {
                    "sClass": "txt-align-left",
                    "aTargets": [ 2 ]
                },
                {
                    "aTargets": [ 3 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, type, full) {
                        var sourcesLength = full.sources !== undefined ? full.sources.length : 0;
                        return hbBuildQueue({showsources: true, sources: full.sources, codebase: full.codebase, sourcesLength: sourcesLength});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        var $jsonPopup = $(nTd).find('a.popup-btn-json-js');
                        popup.initJSONPopup($jsonPopup, {showCodebases: oData});
                    }
                },
                {
                    "aTargets": [ 4 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, type, full) {
                        var requested = moment.unix(full.submittedAt).format('MMMM Do YYYY, H:mm:ss');
                        return hbBuildQueue({reason: full.reason, requested: requested, submittedAt: full.submittedAt});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        timeElements.addElapsedElem($(nTd).find('.waiting-time'), oData.submittedAt);
                    }
                },
                {
                    "aTargets": [ 5 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, type, full) {
                        var slavelength = full.slaves !== undefined ? full.slaves.length : 0;
                        return hbBuildQueue({showslaves: true, slaves: data, slavelength: slavelength});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        var $jsonPopup = $(nTd).find('a.popup-btn-json-js');
                        popup.initJSONPopup($jsonPopup, {showCompatibleSlaves: oData});
                    }
                },
                {
                    "aTargets": [ 6 ],
                    "sClass": "select-input",
                    "mRender": function (data, type, full) {
                        return hbBuildQueue({input: 'true', brid: full.brid});
                    }

                }
            ];

            return dt.initTable($('.buildqueue-table'), options);
        }
    };

    return rtBuildQueue;
});