define(['jquery', 'realtimePages', 'helpers', 'dataTables', 'mustache', 'text!templates/buildslaves.mustache'], function ($, realtimePages, helpers, dt, mustache, buildslaves) {
    "use strict";
    var rtBuildSlaves;
    var tbsorter = undefined;

    rtBuildSlaves = {
        init: function () {
            tbsorter = rtBuildSlaves.dataTableInit($('.buildslaves-table'));
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions["slaves"] = rtBuildSlaves.processBuildSlaves;
            realtimePages.initRealtime(realtimeFunctions);
        },
        processBuildSlaves: function (data) {
            tbsorter.fnClearTable();
            try {
                //Buildbot doesn't easily give you an array so we are running through a dictionary here
                $.each(data, function (key, value) {
                    var arObjData = [value];
                    tbsorter.fnAddData(arObjData);
                });
            }
            catch (err) {
            }
        },
        dataTableInit: function ($tableElem) {
            var options = {};

            options.aoColumns = [
                { "mData": null , "bSortable" : true},
                { "mData": null , "bSortable" : false},
                { "mData": null , "bSortable" : true},
                { "mData": null },
                { "mData": null }
            ];

            options.aoColumnDefs = [
                {
                    "aTargets": [ 0 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, full, type) {
                        return mustache.render(buildslaves, {showFriendlyName: true, friendly_name: type.friendly_name, host_name: type.name});
                    }
                },
                {
                    "aTargets": [ 1 ],
                    "sClass": "txt-align-left",
                    "mRender": function () {
                        return mustache.render(buildslaves, {buildersPopup: true});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        $(nTd).find('a.popup-btn-json-js').data({showBuilders: oData});
                    }
                },
                {
                    "aTargets": [ 2 ],
                    "sClass": "txt-align-left",
                    "mRender": function (data, full, type) {
                        return type.name != undefined ? type.name : 'Not Available';
                    }
                },
                {
                    "aTargets": [ 3 ],
                    "mRender": function (data, full, type) {
                        var statusTxt;
                        var overtime = 0;
                        if (type.connected === undefined || type.connected === false) {
                            statusTxt = 'Offline';
                        }
                        else if (type.connected === true && type.runningBuilds === undefined) {
                            statusTxt = 'Idle';
                        } else if (type.connected === true && type.runningBuilds.length > 0) {
                            statusTxt = type.runningBuilds.length + ' build(s) ';
                            var spinIcon = true;
                        }
                        if (type.runningBuilds != undefined) {

                            $.each(type.runningBuilds, function (key, value) {
                                if (value.eta != undefined && value.eta < 0) {
                                    overtime++
                                }
                            });
                            overtime = overtime > 0 ? overtime : false;
                        }
                        return mustache.render(buildslaves, {showStatusTxt: statusTxt, showSpinIcon: spinIcon, showOvertime: overtime});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        if (oData.connected === undefined) {
                            $(nTd).addClass('offline');
                        }
                        else if (oData.connected === true && oData.runningBuilds === undefined) {
                            $(nTd).addClass('idle');
                        } else if (oData.connected === true && oData.runningBuilds.length > 0) {
                            $(nTd).addClass('building').find('a.popup-btn-json-js').data({showRunningBuilds: oData});
                        }
                    }

                },
                {
                    "aTargets": [ 4 ],
                    "mRender": function (data, full, type) {
                        var showTimeago = type.lastMessage != undefined ? true : null;
                        var lastMessageDate = showTimeago ? ' (' + moment.unix(type.lastMessage).format('MMM Do YYYY, H:mm:ss') + ')' : '';
                        return mustache.render(buildslaves, {showTimeago: showTimeago, showLastMessageDate: lastMessageDate});
                    },
                    "fnCreatedCell": function (nTd, sData, oData) {
                        helpers.startCounterTimeago($(nTd).find('.last-message-timemago'), oData.lastMessage);
                    }

                }

            ];

            return dt.initTable($tableElem, options);
        }
    };
    return rtBuildSlaves;
});