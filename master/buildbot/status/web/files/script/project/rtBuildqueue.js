/*global define, moment*/
define(['jquery', 'realtimePages', 'helpers', 'dataTables', 'mustache', 'text!templates/buildqueue.mustache', 'timeElements', 'popup'], function ($, realtimePages, helpers, dt, Mustache, buildqueue, timeElements, popup) {
    "use strict";
    var tbsorter,
        rtBuildQueue;

    rtBuildQueue = {
        init: function () {
            tbsorter = rtBuildQueue.dataTableInit();

            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.queue = rtBuildQueue.processBuildQueue;
            realtimePages.initRealtime(realtimeFunctions);
            // check all in tables and remove builds
            helpers.selectBuildsAction(tbsorter, '', '/buildqueue/_selected/cancelselected', 'cancelselected=');

        },
        processBuildQueue: function (data) {
            timeElements.clearTimeObjects(tbsorter);
            tbsorter.fnClearTable();
            try {
                tbsorter.fnAddData(data);
                timeElements.updateTimeObjects();
            } catch (err) {
            }
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
                    "mRender": function (data, full, type) {
                        var sourcesLength = type.sources.length;
                        return Mustache.render(buildqueue, {showsources: true, sources: type.sources, codebase: type.codebase, sourcesLength: sourcesLength});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        var $jsonPopup = $(nTd).find('a.popup-btn-json-js');
                        popup.initJSONPopup($jsonPopup, {showCodebases: oData});
                    }
                },
                {
                    "aTargets": [ 2 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, full, type) {
                        var requested = moment.unix(type.submittedAt).format('MMMM Do YYYY, H:mm:ss');
                        return Mustache.render(buildqueue, {reason: type.reason, requested: requested, submittedAt: type.submittedAt});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        timeElements.addElapsedElem($(nTd).find('.waiting-time'), oData.submittedAt);
                    }
                },
                {
                    "aTargets": [ 3 ],
                    "sClass": "txt-align-right",
                    "mRender": function (data, full, type) {
                        var slavelength = type.slaves.length;
                        return Mustache.render(buildqueue, {showslaves: true, slaves: data, slavelength: slavelength});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        var $jsonPopup = $(nTd).find('a.popup-btn-json-js');
                        popup.initJSONPopup($jsonPopup, {showCompatibleSlaves: oData});
                    }
                },
                {
                    "aTargets": [ 4 ],
                    "sClass": "select-input",
                    "mRender": function (data, full, type) {
                        return Mustache.render(buildqueue, {input: 'true', brid: type.brid});
                    }

                }
            ];

            return dt.initTable($('.buildqueue-table'), options);
        }
    };

    return rtBuildQueue;
});