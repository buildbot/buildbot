/*global define, Handlebars*/
define(function (require) {
    "use strict";

    var $ = require('jquery'),
        realtimePages = require('realtimePages'),
        helpers = require('helpers'),
        dt = require('datatables-extend'),
        timeElements = require('timeElements'),
        rtTable = require('rtGenericTable'),
        moment = require('moment'),
        popup = require('ui.popup'),
        hb = require('project/handlebars-extend');

    var rtBuildSlaves,
        $tbSlaves,
        hbSlaves = hb.slaves;

    rtBuildSlaves = {
        init: function () {
            $tbSlaves = rtBuildSlaves.dataTableInit($('.buildslaves-table'));
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.slaves = rtBuildSlaves.processBuildSlaves;
            realtimePages.initRealtime(realtimeFunctions);
        },
        processBuildSlaves: function (data) {
            data = helpers.objectPropertiesToArray(data);
            rtTable.table.rtfGenericTableProcess($tbSlaves, data);
        },
        dataTableInit: function ($tableElem) {
            var options = {};

            options.aoColumns = [
                { "mData": null, "bSortable": true, "sWidth": "10%"},
                { "mData": null, "bSortable": false, "sWidth": "5%"},
                { "mData": null, "bSortable": true, "sWidth": "10%"},
                { "mData": null, "sWidth": "10%"},
                { "mData": null, "sWidth": "10%" },
                { "mData": null, "sWidth": "5%" }
            ];

            options.aoColumnDefs = [
                rtTable.cell.slaveName(0, "friendly_name", "url"),
                {
                    "aTargets": [ 1 ],
                    "sClass": "txt-align-left",
                    "mRender": function () {
                        return hbSlaves({buildersPopup: true});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        var $jsonPopup = $(nTd).find('a.popup-btn-json-js');
                        popup.initJSONPopup($jsonPopup, {showBuilders: oData});
                    }
                },
                {
                    "aTargets": [ 2 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, full, type) {
                        return type.name !== undefined ? type.name : 'Not Available';
                    }
                },
                rtTable.cell.slaveStatus(3),
                {
                    "aTargets": [ 4 ],
                    "mRender": function (data, full, type) {
                        var showTimeago = type.lastMessage !== undefined ? true : null;
                        var lastMessageDate = showTimeago ? ' (' + moment.unix(type.lastMessage).format('MMM Do YYYY, H:mm:ss') + ')' : '';
                        return hbSlaves({showTimeago: showTimeago, showLastMessageDate: lastMessageDate});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        timeElements.addTimeAgoElem($(nTd).find('.last-message-timemago'), oData.lastMessage);
                    }

                },
                rtTable.cell.slaveHealth(5)
            ];

            return dt.initTable($tableElem, options);
        }
    };
    return rtBuildSlaves;
});