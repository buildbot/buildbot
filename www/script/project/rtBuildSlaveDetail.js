/*global define, Handlebars*/
define(function (require) {
    "use strict";

    var $ = require('jquery'),
        realtimePages = require('realtimePages'),
        dt = require('datatables-extend'),
        rtTable = require('rtGenericTable'),
        popup = require('ui.popup'),
        hb = require('project/handlebars-extend');


    require('extend-moment');
    require('libs/jquery.form');
    require('timeElements');

    var hbCells = hb.rtCells,
        hbBuildSlaveDetail = hb.slaveDetail,
        rtBuildSlaveDetail,
        $tbCurrentBuildsTable,
        $tbBuildsTable,
        $slaveInfo;

    var privFunc = {
        initCancelBuild: function () {
            $tbCurrentBuildsTable.delegate("[data-cancel-url]", "click", function () {
                $.ajax($(this).attr("data-cancel-url"));
            });

            $("#cancelAllCurrentBuilds").bind("click.katana", function () {
                var builds = $tbCurrentBuildsTable.find("[data-cancel-url]");
                $.each(builds, function (index, val) {
                    var $input = $(val).parent().find("[name=cancelselected]");
                    if ($input.prop("checked")) {
                        $.ajax($(val).attr("data-cancel-url"));
                    }
                });
            });

            $("#selectAll").bind("click.katana", function () {
                var checked = $(this).prop("checked");
                var builds = $tbCurrentBuildsTable.find("[data-cancel-url]");
                $.each(builds, function (index, val) {
                    var $input = $(val).parent().find("[name=cancelselected]");
                    $input.prop("checked", checked);
                });
            });
        },
        renderSlaveStatus: function renderSlaveStatus($slaveInfo, data) {
            var statusCell = $slaveInfo.find('#slave-status'),
                cellDict = rtTable.cell.slaveStatus(0);

            statusCell.html(cellDict.mRender(undefined, undefined, data));
        }
    };

    rtBuildSlaveDetail = {
        init: function init() {
            $tbCurrentBuildsTable = rtBuildSlaveDetail.currentBuildsTableInit($('#rtCurrentBuildsTable'));
            $tbBuildsTable = rtTable.table.buildTableInit($('#rtBuildsTable'), true);
            $slaveInfo = $('#slaveInfo');

            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.recent_builds = rtBuildSlaveDetail.rtfProcessBuilds;
            realtimeFunctions.slave = rtBuildSlaveDetail.rtfProcessSlaveInfo;
            realtimePages.initRealtime(realtimeFunctions);

            privFunc.initCancelBuild();
        },
        rtfProcessSlaveInfo: function (data) {
            data.shutdownURL = $slaveInfo.attr("data-shutdown-url");
            data.graceful = $slaveInfo.attr("data-graceful") === "True";
            if (data.eid !== -1) {
                data.showEID = true;
            }

            $slaveInfo.html(hbBuildSlaveDetail(data));
            var $jsonPopup = $slaveInfo.find('a.popup-btn-json-js');
            popup.initJSONPopup($jsonPopup, {showBuilders: data});

            privFunc.renderSlaveStatus($slaveInfo, data);
            var $slaveStatusPopup = $slaveInfo.find('div#slave-status a.popup-btn-json-js');
            popup.initJSONPopup($slaveStatusPopup, {showRunningBuilds: data});

            if (data.runningBuilds !== undefined) {
                rtTable.table.rtfGenericTableProcess($tbCurrentBuildsTable, data.runningBuilds);
            }
        },
        rtfProcessBuilds: function (data) {
            rtTable.table.rtfGenericTableProcess($tbBuildsTable, data);
        },
        currentBuildsTableInit: function ($tableElem) {

            var options = {};

            options.oLanguage = {
                "sEmptyTable": "No current builds"
            };

            options.aoColumns = [
                { "mData": null, "sTitle": "Builder", "sWidth": "30%" },
                { "mData": null, "sTitle": "Current build", "sWidth": "30%" },
                { "mData": null, "sTitle": "Revision", "sWidth": "30%" },
                { "mData": null, "sTitle": "Author", "sWidth": "5%"},
                { "mData": null, "sTitle": hbCells({showInputField: true, text: '', inputId: 'selectAll'}), "sWidth": "7%", "sClass": "select-input", 'bSortable': false}
            ];

            options.aoColumnDefs = [
                rtTable.cell.builderName(0, 'txt-align-left'),
                rtTable.cell.buildProgress(1, true),
                rtTable.cell.revision(2, "sourceStamps"),
                {
                    "aTargets": [ 3 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, type, full) {
                        var author = 'N/A';
                        if (full.properties !== undefined) {
                            $.each(full.properties, function (i, prop) {
                                if (prop[0] === "owner") {
                                    author = prop[1];
                                }
                            });
                        }
                        return author;
                    }
                },
                rtTable.cell.stopBuild(4)
            ];

            return dt.initTable($tableElem, options);
        }

    };

    return rtBuildSlaveDetail;
});
