/*global console, Handlebars*/
define(['jquery', 'realtimePages', 'helpers', 'dataTables', 'handlebars', 'extend-moment', 'libs/jquery.form', 'text!templates/builderdetail.handlebars', 'timeElements'], function ($, realtimePages, helpers, dt, hb, extendMoment, form, builderdetail, timeElements) {
    "use strict";
    var rtBuilderDetail,
        $tbCurrentBuildsElem,
        $tbCurrentBuildsTable,
        $tbPendingBuildsTable,
        builderdetailHandle = Handlebars.compile(builderdetail);

    rtBuilderDetail = {
        init: function () {
            $tbCurrentBuildsTable = rtBuilderDetail.currentBuildsTableInit($('#rtCurrentBuildsTable'));
            $tbPendingBuildsTable = rtBuilderDetail.pendingBuildsTableInit($('#rtPendingBuildsTable'));
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();

            realtimeFunctions.project = rtBuilderDetail.rtfProcessCurrentBuilds;
            realtimeFunctions.pending_builds = rtBuilderDetail.rtfProcessPendingBuilds;
            realtimePages.initRealtime(realtimeFunctions);

            // insert codebase and branch
            var $dtWTop = $('.dataTables_wrapper .top');
            if (window.location.search !== '') {
                // Parse the url and insert current codebases and branches
                helpers.codeBaseBranchOverview($('#brancOverViewCont'));
            }
        },
        rtfProcessCurrentBuilds: function (data) {
            timeElements.clearTimeObjects($tbCurrentBuildsTable);
            $tbCurrentBuildsTable.fnClearTable();

            try {
                console.log(data);
                if (data.currentBuilds !== undefined) {
                    $tbCurrentBuildsTable.fnAddData(data.currentBuilds);
                    timeElements.updateTimeObjects();
                }

                timeElements.updateTimeObjects();
            } catch (err) {
                console.log(err);
            }
        },
        rtfProcessPendingBuilds: function (data) {
            timeElements.clearTimeObjects($tbPendingBuildsTable);
            $tbPendingBuildsTable.fnClearTable();
            helpers.selectBuildsAction($tbPendingBuildsTable);

            try {
                console.log(data);
                $tbPendingBuildsTable.fnAddData(data);
                timeElements.updateTimeObjects();
            } catch (err) {

            }
        },
        currentBuildsTableInit: function ($tableElem) {
            var options = {};

            options.aoColumns = [
                { "mData": null },
                { "mData": null },
                { "mData": null },
                { "mData": null }
            ];

            options.aoColumnDefs = [
                {
                    "aTargets": [ 0 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, type, full) {
                        return builderdetailHandle({showNumber: true, 'data': full});
                    }
                },
                {
                    "aTargets": [ 1 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, full, type) {
                        var runningBuilds = {
                            showRunningBuilds: true
                        };
                        var extended = $.extend(runningBuilds, type);
                        return builderdetailHandle(extended);
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        helpers.delegateToProgressBar($(nTd).find('.percent-outer-js'));
                    }
                },
                {
                    "aTargets": [ 2 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, type, full) {
                        return builderdetailHandle({currentBuildRevision: true, 'data': full});
                    }
                },
                {
                    "aTargets": [ 3 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, type, full) {
                        var author = 'N/A';
                        $.each(full.properties, function (i, prop) {
                            if (prop[0] === "owner") {
                                author = prop[1];
                            }
                        });
                        return author;
                    }
                }
            ];

            return dt.initTable($tableElem, options);
        },
        pendingBuildsTableInit: function ($tableElem) {
            var options = {};

            options.aoColumns = [
                { "mData": null },
                { "mData": null },
                { "mData": null }
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
                    "mRender": function (data, type, full) {
                        return builderdetailHandle({pendingBuildWait: true});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        timeElements.addElapsedElem($(nTd).find('.waiting-time-js'), oData.submittedAt);
                    }
                },
                {
                    "aTargets": [ 2 ],
                    "sClass": "txt-align-right",
                    "mRender": function (data, type, full) {
                        return builderdetailHandle({removeBuildSelector: true, data: full});
                    }
                }
            ];

            return dt.initTable($tableElem, options);
        }
    };

    return rtBuilderDetail;
});
