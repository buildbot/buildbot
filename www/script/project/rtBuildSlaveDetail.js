/*global define, Handlebars*/
define(['jquery', 'realtimePages', 'helpers', 'dataTables', 'handlebars', 'extend-moment',
        'libs/jquery.form', 'text!templates/builderdetail.handlebars', 'text!hbCells', 'timeElements', 'rtGenericTable', 'popup'],
    function ($, realtimePages, helpers, dt, hb, extendMoment, form, builderdetail, hbCellsText, timeElements, rtTable, popup) {
        "use strict";

        var hbCells = Handlebars.compile(hbCellsText);
        var rtBuildSlaveDetail,
            $tbCurrentBuildsTable,
            $tbBuildsTable,
            builderdetailHandle = Handlebars.compile(builderdetail);

        var privFunc = {
            initCancelBuild: function () {
                $tbCurrentBuildsTable.delegate("[data-cancel-url]", "click", function (e) {
                    $.ajax($(this).attr("data-cancel-url"));
                });

                $("#cancelAllCurrentBuilds").click(function () {
                    var builds = $tbCurrentBuildsTable.find("[data-cancel-url]");
                    $.each(builds, function (index, val) {
                        var $input = $(val).parent().find("[name=cancelselected]");
                        if ($input.prop("checked")) {
                            $.ajax($(val).attr("data-cancel-url"));
                        }
                    });
                });

                $("#selectAll").click(function () {
                    var checked = $(this).prop("checked");
                    var builds = $tbCurrentBuildsTable.find("[data-cancel-url]");
                    $.each(builds, function (index, val) {
                        var $input = $(val).parent().find("[name=cancelselected]");
                        $input.prop("checked", checked);
                    });
                });
            }
        };

        rtBuildSlaveDetail = {
            init: function () {
                $tbCurrentBuildsTable = rtBuildSlaveDetail.currentBuildsTableInit($('#rtCurrentBuildsTable'));
                $tbBuildsTable = rtTable.table.buildTableInit($('#rtBuildsTable'), true);

                var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
                realtimeFunctions.current_builds = rtBuildSlaveDetail.rtfProcessCurrentBuilds;
                realtimeFunctions.recent_builds = rtBuildSlaveDetail.rtfProcessBuilds;
                realtimePages.initRealtime(realtimeFunctions);

                privFunc.initCancelBuild();
            },
            rtfProcessCurrentBuilds: function (data) {
                rtTable.table.rtfGenericTableProcess($tbCurrentBuildsTable, data);
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
                    { "mData": null, "sTitle": hbCells({showInputField: true, text: 'Select all', inputId: 'selectAll'}), "sWidth": "5%", "sClass": "select-input", 'bSortable': false}
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
