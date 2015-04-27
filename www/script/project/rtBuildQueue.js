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

            options.aaSorting = [
                [ 2, "asc" ]
            ];

            options.aoColumns = [
                { "mData": "builderFriendlyName" },
                { "mData": "sources" },
                { "mData": "reason"},
                { "mData": "slaves" },
                { "mData": "brid" }
            ];

            options.aoColumnDefs = [
                {
                    "sClass": "txt-align-left",
                    "aTargets": [ 0 ]
                },
                {
                    "aTargets": [ 1 ],
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
                    "aTargets": [ 2 ],
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
                    "aTargets": [ 3 ],
                    "sClass": "txt-align-right",
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
                    "aTargets": [ 4 ],
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