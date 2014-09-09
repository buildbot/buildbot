/*global define*/
define(function (require) {
    "use strict";

    var $ = require('jquery'),
        dt = require('datatables-extend'),
        timeElements = require('timeElements'),
        extendMoment = require('extend-moment'),
        helpers = require('helpers'),
        moment = require('moment'),
        popup = require('ui.popup'),
        URI = require('URIjs/URI'),
        hb = require('project/handlebars-extend');

    var rtCells = hb.rtCells;

    var privFunc = {
        getPropertyOnData: function (data, property) {
            if (property === undefined) {
                return data;
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
                    return rtCells({
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
                    return rtCells({buildID: true, 'data': full});
                }
            };
        },
        buildStatus: function (index, property, className) {
            return {
                "aTargets": [index],
                "sClass": className === undefined ? "txt-align-left" : className,
                "mRender": function (data, type, full) {
                    var build = privFunc.getPropertyOnData(full, property);
                    if (build !== undefined) {
                        if (typeof build.url === "object") {
                            build = $.extend({}, build, {url: build.url.path});
                        }
                        return hb.partials.cells["cells:buildStatus"](build);
                    }

                    return "";
                },
                "fnCreatedCell": function (nTd, sData, oData) {
                    var build = privFunc.getPropertyOnData(oData, property);
                    if (build !== undefined) {
                        $(nTd).removeClass().addClass(build.results_text);
                    }
                }
            };
        },
        builderName: function (index, className) {
            return {
                "aTargets": [index],
                "sClass": className === undefined ? "txt-align-right" : className,
                "mRender": function (data, type, full) {
                    if (full.builderFriendlyName !== undefined) {
                        full = $.extend({}, full, {url: full.builder_url});
                        full.friendly_name = full.builderFriendlyName;
                    }
                    return hb.partials.cells["cells:builderName"](full);
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
                    return rtCells({slaveName: true, 'name': name, 'url': url});
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
                    } else if (type.connected === true && (type.runningBuilds === undefined || type.runningBuilds.length === 0)) {
                        statusTxt = 'Idle';
                    } else if (type.connected === true && type.runningBuilds.length > 0) {
                        statusTxt = type.runningBuilds.length + ' build(s) ';
                        isRunning = true;
                    }
                    return rtCells({slaveStatus: true, showStatusTxt: statusTxt, showSpinIcon: isRunning});
                },
                "fnCreatedCell": function (nTd, sData, oData) {
                    if (oData.connected === undefined) {
                        $(nTd).addClass('offline');
                    } else if (oData.connected === true && oData.runningBuilds === undefined) {
                        $(nTd).addClass('idle');
                    } else if (oData.connected === true && oData.runningBuilds.length > 0) {
                        var overtime = false;
                        if (oData.runningBuilds !== undefined) {

                            $.each(oData.runningBuilds, function (key, value) {
                                if (value.eta !== undefined && value.eta < 0) {
                                    overtime = true;
                                }
                            });
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
        slaveHealth: function (index) {
            return {
                "aTargets": [index],
                "mRender": function (data, type, full) {
                    if (full.health === undefined) {
                        full.health = 0;
                    }
                    if (type === 'sort') {
                        return -full.health;
                    }
                    return rtCells({slaveHealthCell: true, health: full.health});
                },
                "sType": "numeric"
            };
        },
        buildProgress: function (index, singleBuild) {
            return {
                "aTargets": [index],
                "sClass": "txt-align-left",
                "mRender": function (data, full, type) {
                    return rtCells({
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

                    return rtCells({
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
                        if (type === 'sort') {
                            if (times.length === 3) {
                                return times[2] - times[0];
                            }
                            return times[1] - times[0];
                        }

                        var d = moment.duration((times[1] - times[0]) * 1000);
                        if (times.length === 3) {
                            d = moment.duration((times[2] - times[0]) * 1000);
                        }
                        if (d.hours() > 0) {
                            return "{0}h {1}m {2}s".format(d.hours(), d.minutes(), d.seconds());
                        }
                        return "{0}m {1}s".format(d.minutes(), d.seconds());
                    }

                    if (type === 'sort') {
                        return 0;
                    }
                    return "N/A";
                }
            };
        },
        buildLastRun: function (index) {
            return {
                "aTargets": [index],
                "sClass": "txt-align-left last-build-js",
                "mRender": function (data, type, full) {
                    if (type === "sort") {
                        if (full.latestBuild !== undefined) {
                            return full.latestBuild.times[1];
                        }
                        return 0;
                    }
                    return hb.partials.cells["cells:buildLastRun"](full.latestBuild);
                },
                "fnCreatedCell": function (nTd, sData, oData) {
                    if (oData.latestBuild !== undefined) {
                        timeElements.addTimeAgoElem($(nTd).find('.last-run'), oData.latestBuild.times[1]);
                        var time = helpers.getTime(oData.latestBuild.times[0], oData.latestBuild.times[1]).trim();
                        $(nTd).find('.small-txt').html('(' + time + ')');
                        $(nTd).find('.hidden-date-js').html(oData.latestBuild.times[1]);
                    }
                }
            };
        },
        buildShortcuts: function (index, property) {
            return {
                "aTargets": [index],
                "mRender": function (data, type, full) {
                    var build = privFunc.getPropertyOnData(full, property);
                    if (build !== undefined) {
                        return hb.partials.cells["cells:buildShortcuts"](build);
                    }

                    return "";
                },
                "fnCreatedCell": function (nTd, sData, oData) {
                    var build = privFunc.getPropertyOnData(oData, property);
                    if (build !== undefined && build.artifacts !== undefined) {
                        popup.initArtifacts(build.artifacts, $(nTd).find(".artifact-js"));
                    }
                }
            };
        }
    };

    var tableFunc = {
        buildTableInit: function ($tableElem, showBuilderName, hideBranches) {
            var options = {};

            options.aoColumns = [
                { "mData": null, "sTitle": "#", "sWidth": "10%" },
                { "mData": null, "sTitle": "Date", "sWidth": "15%" },
                { "mData": null, "sTitle": "Revision", "sWidth": "20%" },
                { "mData": null, "sTitle": "Result", "sWidth": "30%", "sClass": "txt-align-left"},
                { "mData": null, "sTitle": "Build Time", "sWidth": "10%" },
                { "mData": null, "sTitle": "Slave", "sWidth": "15%" }
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
            helpers.clearChildEvents($table);

            // Remove all cells manually making sure events are correctly removed
            $table.find("tbody tr :not([class=dataTables_empty])").remove();
            $table.fnClearTable(true);

            try {
                $table.fnAddData(data);
                timeElements.updateTimeObjects();
            } catch (ignore) {
            }
        }

    };

    return {
        table: tableFunc,
        cell: cellFunc
    };
});
