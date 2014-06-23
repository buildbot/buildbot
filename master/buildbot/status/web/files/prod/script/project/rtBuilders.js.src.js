/*global define*/
define(['jquery', 'realtimePages', 'helpers', 'dataTables', 'mustache', 'libs/jquery.form', 'text!templates/builders.mustache', 'timeElements', 'rtGenericTable', 'popup','toastr'], function ($, realtimePages, helpers, dt, mustache, form, builders, timeElements, rtTable, popup, toastr) {
    
    var rtBuilders,
        $tbsorter;


    rtBuilders = {
        init: function () {
            $tbsorter = rtBuilders.dataTableInit($('.builders-table'));
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.builders = rtBuilders.realtimeFunctionsProcessBuilders;
            realtimePages.initRealtime(realtimeFunctions);

            // insert codebase and branch on the builders page
            var $dtWTop = $('.dataTables_wrapper .top');
            if (window.location.search !== '') {
                // Parse the url and insert current codebases and branches
                helpers.codeBaseBranchOverview($dtWTop);
            }
        },
        realtimeFunctionsProcessBuilders: function (data) {
            rtTable.table.rtfGenericTableProcess($tbsorter, data.builders);
        },
        dataTableInit: function ($tableElem) {
            var options = {};

            options.aoColumns = [
                { "mData": null, "sWidth": "20%" },
                { "mData": null, "sWidth": "15%" },
                { "mData": null, "sWidth": "10%" },
                { "mData": null, "sWidth": "15%", "sType": "builder-status" },
                { "mData": null, "sWidth": "5%", "bSortable": false  },
                { "mData": null, "sWidth": "15%", "bSortable": false  },
                { "mData": null, "sWidth": "10%", "sType": "natural" },
                { "mData": null, "sWidth": "10%", "bSortable": false }
            ];

            options.aoColumnDefs = [
                {
                    "aTargets": [ 0 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, full, type) {
                        return mustache.render(builders, {name: type.name, friendly_name: type.friendly_name, url: type.url});
                    }
                },
                rtTable.cell.buildProgress(1, false),
                {
                    "aTargets": [ 2 ],
                    "sClass": "txt-align-left last-build-js",
                    "mRender": function (data, type, full) {
                        return mustache.render(builders, {showLatestBuild: true, latestBuild: full.latestBuild});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        if (oData.latestBuild !== undefined) {
                            timeElements.addTimeAgoElem($(nTd).find('.last-run'), oData.latestBuild.times[1]);
                            var time = helpers.getTime(oData.latestBuild.times[0], oData.latestBuild.times[1]).trim();
                            $(nTd).find('.small-txt').html('(' + time + ')');
                            $(nTd).find('.hidden-date-js').html(oData.latestBuild.times[1]);
                        }
                    }
                },
                {
                    "aTargets": [ 3 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, type, full) {
                        if (type === 'sort') {
                            return full;
                        }
                        return mustache.render(builders, {showStatus: true, latestBuild: full.latestBuild, data: full});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        var lb = oData.latestBuild === undefined ? '' : oData.latestBuild;
                        $(nTd).removeClass().addClass(lb.results_text);
                    }
                },
                {
                    "aTargets": [4],
                    "mRender": function (data, full, type) {
                        return mustache.render(builders, {showShortcuts: true, data: type});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        if (oData.latestBuild !== undefined && oData.latestBuild.artifacts !== undefined) {
                            popup.initArtifacts(oData.latestBuild.artifacts, $(nTd).find(".artifact-js"));
                        }
                    }
                },
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
                        return mustache.render(builders, {customBuild: true, url: type.url, builderName: type.name});
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
