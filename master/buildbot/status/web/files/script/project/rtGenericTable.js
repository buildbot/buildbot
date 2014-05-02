/*global define, Handlebars*/
define(['jquery', 'dataTables', 'timeElements', 'text!hbCells', 'extend-moment', 'handlebars'], function ($, dt, timeElements, hbCellsText, extendMoment) {

    "use strict";

    var hbCells = Handlebars.compile(hbCellsText);

    var privFunc = {
        getPropertyOnData: function (data, property) {
            if (property instanceof String) {
                return data[property];
            }

            return property(data);
        }
    };

    var cellFunc = {
        revision: function (index) {
            return {
                "aTargets": [index],
                "sClass": "txt-align-left",
                "mRender": function (data, type, full) {
                    return hbCells({revisionCell: true, 'data': full});
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
        buildStatus: function (index) {
            return {
                "aTargets": [index],
                "sClass": "txt-align-left",
                "mRender": function (data, type, full) {
                    return hbCells({buildStatus: true, 'build': full});
                },
                "fnCreatedCell": function (nTd, sData, oData) {
                    $(nTd).removeClass().addClass(oData.results_text);
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
        }
    };

    var tableFunc = {
        buildTableInit: function ($tableElem) {
            var options = {};

            options.aoColumns = [
                { "mData": null, "sTitle": "#" },
                { "mData": null, "sTitle": "Date", "sWidth": "50px" },
                { "mData": null, "sTitle": "Revision" },
                { "mData": null, "sTitle": "Result" },
                { "mData": null, "sTitle": "Slave", "sWidth": "110px" }
            ];

            options.aoColumnDefs = [
                cellFunc.buildID(0),
                cellFunc.shortTime(1, function (data) {
                    return data.times[0];
                }),
                cellFunc.revision(2),
                cellFunc.buildStatus(3),
                {
                    "aTargets": [4],
                    "sClass": "txt-align-left",
                    "mRender": function (data, type, full) {
                        return full.slave_friendly_name;
                    }
                }
            ];

            return dt.initTable($tableElem, options);
        },
        rtfProcessBuilds: function ($table, data) {
            timeElements.clearTimeObjects($table);
            $table.fnClearTable();

            try {
                $table.fnAddData(data);
                timeElements.updateTimeObjects();

            } catch (err) { }
        }

    };

    return {
        table: tableFunc,
        cell: cellFunc
    };
});