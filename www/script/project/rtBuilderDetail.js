/*global define*/
define(function (require) {
    "use strict";

    var $ = require('jquery'),
        realtimePages = require('realtimePages'),
        helpers = require('helpers'),
        dt = require('project/datatables-extend'),
        hb = require('project/handlebars-extend'),
        extendMoment = require('project/moment-extend'),
        timeElements = require('timeElements'),
        rtTable = require('rtGenericTable'),
        popup = require('ui.popup'),
        URI = require('libs/uri/URI');

    require('libs/jquery.form');

    var rtBuilderDetail,
        $tbCurrentBuildsTable,
        $tbPendingBuildsTable,
        $tbBuildsTable,
        $tbSlavesTable,
        hbBuilderDetail = hb.builderDetail;

    rtBuilderDetail = {
        init: function () {
            $tbCurrentBuildsTable = rtBuilderDetail.currentBuildsTableInit($('#rtCurrentBuildsTable'));
            $tbPendingBuildsTable = rtBuilderDetail.pendingBuildsTableInit($('#rtPendingBuildsTable'));
            $tbBuildsTable = rtTable.table.buildTableInit($('#rtBuildsTable'), false, helpers.urlHasCodebases());
            $tbSlavesTable = rtBuilderDetail.slavesTableInit($('#rtSlavesTable'));

            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.project = rtBuilderDetail.rtfProcessCurrentBuilds;
            realtimeFunctions.pending_builds = rtBuilderDetail.rtfProcessPendingBuilds;
            realtimeFunctions.builds = rtBuilderDetail.rtfProcessBuilds;
            realtimeFunctions.slaves = rtBuilderDetail.rtfProcessSlaves;

            realtimePages.initRealtime(realtimeFunctions);

            helpers.selectBuildsAction($tbPendingBuildsTable, false, '/buildqueue/_selected/cancelselected',
                'cancelselected=', rtTable.table.rtfGenericTableProcess);

            //Setup run build
            popup.initRunBuild($(".custom-build"));

            // insert codebase and branch
            helpers.codeBaseBranchOverview($('#brancOverViewCont'));

            var args = URI.parseQuery(window.location.search);

            var tags = {
                results: [
                    {id: "0", text: "Success"},
                    {id: "1", text: "Warnings"},
                    {id: "2", text: "Failure"},
                    {id: "3", text: "Skipped"},
                    {id: "4", text: "Exception"},
                    {id: "5", text: "Retry"},
                    {id: "6", text: "Canceled"},
                    {id: "7", text: "Not Rebuilt"},
                    {id: "8", text: "Dependency Failure"}
                ]
            };

            var $buildResultSelector = $("#buildResultSelector"),
                $numBuildsSelector = $("#numBuildsSelector");

            $buildResultSelector.val(args.results).select2({"multiple": true,
                                                            "data": tags});

            // Set the value of the numBuildsSelector defaulting to 15 for when not found,
            // change location on change of the value and initialize select2
            $numBuildsSelector.val(args.numbuilds || 15).select2({minimumResultsForSearch: -1});

            $("#btnFilter").bind("click.katana", function changeNumBuilds() {
                var numBuilds = $numBuildsSelector.val();


                var url = URI(window.location.href).setQuery({numbuilds: numBuilds});

                var results_tags = $buildResultSelector.val();
                if (results_tags.length > 0) {
                    url.setQuery("results", results_tags.split(","));
                } else {
                    url.removeQuery("results");
                }

                window.location = url;
            });
        },
        rtfProcessCurrentBuilds: function (data) {
            if (data.currentBuilds !== undefined) {
                rtTable.table.rtfGenericTableProcess($tbCurrentBuildsTable, data.currentBuilds);
            }
        },
        rtfProcessPendingBuilds: function (data) {
            rtTable.table.rtfGenericTableProcess($tbPendingBuildsTable, data);
        },
        rtfProcessSlaves: function (data) {
            data = helpers.objectPropertiesToArray(data);
            rtTable.table.rtfGenericTableProcess($tbSlavesTable, data);
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
                { "mData": null, "sTitle": "#", "sWidth": "10%"  },
                { "mData": null, "sTitle": "Current build", "sWidth": "30%" },
                { "mData": null, "sTitle": "Revision", "sWidth": "35%" },
                { "mData": null, "sTitle": "Author", "sWidth": "25%", "sClass": "txt-align-right"}
            ];

            options.aoColumnDefs = [
                rtTable.cell.buildID(0),
                rtTable.cell.buildProgress(1, true),
                rtTable.cell.revision(2, "sourceStamps", helpers.urlHasCodebases()),
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
                }
            ];

            return dt.initTable($tableElem, options);
        },
        pendingBuildsTableInit: function ($tableElem) {
            var options = {};

            options.oLanguage = {
                "sEmptyTable": "No pending builds"
            };

            options.aoColumns = [
                { "mData": null, "sWidth": "28%" },
                { "mData": null, "sWidth": "28%" },
                { "mData": null, "sWidth": "28%" },
                { "mData": null, "sWidth": "16%" }
            ];

            options.aoColumnDefs = [
                {
                    "aTargets": [ 0 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, type, full) {
                        return extendMoment.getDateFormatted(full.submittedAt);
                    }
                },
                {
                    "aTargets": [ 1 ],
                    "sClass": "txt-align-left",
                    "mRender": function () {
                        return hbBuilderDetail({pendingBuildWait: true});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        timeElements.addElapsedElem($(nTd).find('.waiting-time-js'), oData.submittedAt);
                    }
                },
                rtTable.cell.revision(2, "sources", helpers.urlHasCodebases()),
                {
                    "aTargets": [ 3 ],
                    "sClass": "txt-align-right",
                    "mRender": function (data, type, full) {
                        return hbBuilderDetail({removeBuildSelector: true, data: full});
                    }
                }
            ];

            return dt.initTable($tableElem, options);
        },
        slavesTableInit: function ($tableElem) {
            var options = {};

            options.oLanguage = {
                "sEmptyTable": "No slaves attached"
            };

            options.aoColumns = [
                { "mData": null, "sWidth": "50%", "sTitle": "Slave" },
                { "mData": null, "sWidth": "50%", "sTitle": "Status" }
            ];

            options.aoColumnDefs = [
                rtTable.cell.slaveName(0, "friendly_name", "url"),
                rtTable.cell.slaveStatus(1)
            ];

            return dt.initTable($tableElem, options);
        }
    };

    return rtBuilderDetail;
});
