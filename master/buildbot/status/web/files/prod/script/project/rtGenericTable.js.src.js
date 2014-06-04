/*global define, Handlebars*/
define(['jquery', 'dataTables', 'timeElements', 'text!hbCells', 'extend-moment', 'handlebars', 'helpers', 'moment', 'popup', 'URIjs/URI'], function ($, dt, timeElements, hbCellsText, extendMoment, hb, helpers, moment, popup, URI) {

    

    var hbCells = Handlebars.compile(hbCellsText);

    var privFunc = {
        getPropertyOnData: function (data, property) {
            if (property === undefined) {
                return undefined;
            }

            if (typeof property === 'string' || property instanceof String) {
                return data[property];
            }

            return property(data);
        },
        buildIsHistoric: function (properties) {
            var hasRevision = false;
            var isDependency = false;
            $.each(properties, function (i, obj) {
                if (obj.length > 0) {
                    if (obj.length === 2 && obj[0] === "revision" && obj[1].length !== 0) {
                        hasRevision = true;
                    } else if (obj.length === 3 && obj[0] === "buildLatestRev" && obj[2] === "Trigger") {
                        isDependency = true;
                    }
                }
            });

            return hasRevision === true && isDependency === false;
        }
    };

    var cellFunc = {
        revision: function (index, property, hideBranch) {
            return {
                "aTargets": [index],
                "sClass": "txt-align-left",
                "mRender": function (data, type, full) {
                    var sourceStamps = privFunc.getPropertyOnData(full, property);
                    var history_build = false;
                    if (full.properties !== undefined) {
                        history_build = privFunc.buildIsHistoric(full.properties);
                    }
                    return hbCells({
                        revisionCell: true,
                        sourceStamps: sourceStamps,
                        history_build: history_build,
                        hide_branch: hideBranch
                    });
                }
            };
        },
        buildID: function (index) {
            return {
                "aTargets": [index],
                "sClass": "txt-align-left",
                "mRender": function (data, type, full) {
                    return hbCells({buildID: true, 'data': full});
                }
            };
        },
        buildStatus: function (index, className) {
            return {
                "aTargets": [index],
                "sClass": className === undefined ? "txt-align-left" : className,
                "mRender": function (data, type, full) {
                    return hbCells({buildStatus: true, 'build': full});
                },
                "fnCreatedCell": function (nTd, sData, oData) {
                    $(nTd).removeClass().addClass(oData.results_text);
                }
            };
        },
        builderName: function (index, className) {
            return {
                "aTargets": [index],
                "sClass": className === undefined ? "txt-align-right" : className,
                "mRender": function (data, type, full) {
                    return hbCells({showBuilderName: true, 'data': full});
                }
            };
        },
        shortTime: function (index, property) {
            return {
                "aTargets": [index],
                "sClass": "txt-align-left",
                "mRender": function (data, type, full) {
                    var time = privFunc.getPropertyOnData(full, property);
                    return extendMoment.getDateFormatted(time);
                }
            };
        },
        slaveName: function (index, slaveNameProperty, slaveURLProperty, className) {
            return {
                "aTargets": [index],
                "sClass": className === undefined ? "txt-align-left" : className,
                "mRender": function (data, type, full) {
                    var name = privFunc.getPropertyOnData(full, slaveNameProperty);
                    var url = privFunc.getPropertyOnData(full, slaveURLProperty);
                    return hbCells({slaveName: true, 'name': name, 'url': url});
                }
            };
        },
        slaveStatus: function (index) {
            return {
                "aTargets": [index],
                "mRender": function (data, full, type) {
                    var statusTxt,
                        isRunning = false;
                    if (type.connected === undefined || type.connected === false) {
                        statusTxt = 'Offline';
                    } else if (type.connected === true && type.runningBuilds === undefined) {
                        statusTxt = 'Idle';
                    } else if (type.connected === true && type.runningBuilds.length > 0) {
                        statusTxt = type.runningBuilds.length + ' build(s) ';
                        isRunning = true;
                    }
                    return hbCells({slaveStatus: true, showStatusTxt: statusTxt, showSpinIcon: isRunning});
                },
                "fnCreatedCell": function (nTd, sData, oData) {
                    if (oData.connected === undefined) {
                        $(nTd).addClass('offline');
                    } else if (oData.connected === true && oData.runningBuilds === undefined) {
                        $(nTd).addClass('idle');
                    } else if (oData.connected === true && oData.runningBuilds.length > 0) {
                        var overtime = 0;
                        if (oData.runningBuilds !== undefined) {

                            $.each(oData.runningBuilds, function (key, value) {
                                if (value.eta !== undefined && value.eta < 0) {
                                    overtime += 1;
                                }
                            });
                            overtime = overtime > 0 ? overtime : false;
                        }

                        var $jsonPopup = $(nTd).addClass('building').find('a.popup-btn-json-js');
                        popup.initJSONPopup($jsonPopup, {showRunningBuilds: oData});

                        if (overtime) {
                            $(nTd).removeClass('building')
                                .addClass('overtime tooltip')
                                .attr('title', "One or more builds on overtime");

                            helpers.tooltip($(nTd));
                        }
                    }
                }
            };
        },
        buildProgress: function (index, singleBuild) {
            return {
                "aTargets": [index],
                "sClass": "txt-align-left",
                "mRender": function (data, full, type) {
                    return hbCells({
                        buildProgress: true,
                        showPending: !singleBuild,
                        pendingBuilds: singleBuild ? undefined : type.pendingBuilds,
                        currentBuilds: singleBuild ? [type] : type.currentBuilds,
                        builderName: type.name
                    });
                },
                "fnCreatedCell": function (nTd) {
                    var bars = $(nTd).find('.percent-outer-js');
                    $.each(bars, function (key, elem) {
                        var obj = $(elem);
                        timeElements.addProgressBarElem(obj, obj.attr('data-starttime'), obj.attr('data-etatime'));
                    });

                    popup.initPendingPopup($(nTd).find(".pending-popup"));
                }
            };
        },
        stopBuild: function (index) {
            return {
                "aTargets": [index],
                "sClass": "txt-align-left",
                "mRender": function (data, full, type) {
                    var stopURL = URI(type.url.path);
                    stopURL = stopURL.path(stopURL.path() + "/stop");

                    return hbCells({
                        stopBuild: true,
                        'data': type,
                        stopURL: stopURL
                    });
                }
            };
        },
        buildLength: function (index, timesProperty) {
            return {
                "aTargets": [index],
                "sClass": "txt-align-left",
                "mRender": function (data, type, full) {
                    var times = privFunc.getPropertyOnData(full, timesProperty);
                    if (times !== undefined) {
                        var d = moment.duration((times[1] - times[0]) * 1000);
                        if (times.length === 3) {
                            d = moment.duration((times[2] - times[0]) * 1000);
                        }
                        return "{0}m {1}s ".format(d.minutes(), d.seconds());
                    }
                    return "N/A";
                }
            };
        }
    };

    var tableFunc = {
        buildTableInit: function ($tableElem, showBuilderName, hideBranches) {
            var options = {};

            options.aoColumns = [
                { "mData": null, "sTitle": "#", "sWidth": "5%" },
                { "mData": null, "sTitle": "Date", "sWidth": "10%" },
                { "mData": null, "sTitle": "Revision", "sWidth": "30%" },
                { "mData": null, "sTitle": "Result", "sWidth": "30%", "sClass": ""},
                { "mData": null, "sTitle": "Build Time", "sWidth": "15%" },
                { "mData": null, "sTitle": "Slave", "sWidth": "10%" }
            ];

            options.fnRowCallback = function (nRow, aData) {
                if (aData.properties !== undefined && privFunc.buildIsHistoric(aData.properties)) {
                    $(nRow).addClass("italic");
                }
            };

            options.aoColumnDefs = [
                cellFunc.buildID(0),
                cellFunc.shortTime(1, function (data) {
                    return data.times[0];
                }),
                cellFunc.revision(2, "sourceStamps", hideBranches),
                cellFunc.buildStatus(3),
                cellFunc.buildLength(4, "times"),
                cellFunc.slaveName(5, function (data) {
                    if (data.slave_friendly_name !== undefined) {
                        return data.slave_friendly_name;
                    }
                    return data.slave;
                }, "slave_url", "txt-align-right")
            ];

            if (showBuilderName === true) {
                options.aoColumns[1].sWidth = '10%';
                options.aoColumns[2].sWidth = '25%';
                options.aoColumns[3].sWidth = '30%';
                options.aoColumns[4].sWidth = '10%';
                options.aoColumns[5].sWidth = '20%';
                options.aoColumns[5].sTitle = 'Builder';

                options.aoColumnDefs.splice(5, 1);
                options.aoColumnDefs.push(cellFunc.builderName(5));
            }

            return dt.initTable($tableElem, options);
        },
        rtfGenericTableProcess: function ($table, data) {
            timeElements.clearTimeObjects($table);
            $table.fnClearTable();

            try {
                $table.fnAddData(data);
                timeElements.updateTimeObjects();
            } catch (err) {
            }
        }

    };

    return {
        table: tableFunc,
        cell: cellFunc
    };
});
