/*global define, Handlebars*/
define(function (require) {
    "use strict";

    var $ = require('jquery'),
        realtimePages = require('realtimePages'),
        helpers = require('helpers'),
        dt = require('project/datatables-extend'),
        rtTable = require('rtGenericTable'),
        hb = require('project/handlebars-extend'),
        selectors = require('selectors'),
        queryString = require('libs/query-string'),
        $tbBuilders = [undefined, undefined],
        rawData = [undefined, undefined];

    var rtComparison = {
        init: function init() {
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();

            realtimeFunctions.codebases = function codebasesRealtime(data) {
                var bData = {
                    builders0: $.extend(true, {}, data.codebases),
                    builders1: $.extend(true, {}, data.codebases)
                };

                $.each(bData, function eachBuilder(i, builder) {
                    $.each(builder, function eachCodebase(y, cb) {
                        var val = data.defaults[i].codebases[y];
                        cb.name = y;

                        if (val !== undefined) {
                            cb.defaultbranch = val[0];
                        }
                    });
                });

                $("#content").html(hb.comparison(
                    {
                        builders: [
                            {id: 0, name: "Left", builderData: bData.builders0},
                            {id: 1, name: "Right", builderData: bData.builders1}
                        ]
                    }
                ));

                $("#submitComparison").bind("click.katana", function openComparisonPage() {
                    var builders = $("[data-builder]"),
                        output = {};

                    $.each(builders, function eachBuilderData(i, b) {
                        var $b = $(b),
                            selects = $b.find("select");

                        output[$b.attr("data-builder")] = "";

                        $.each(selects, function eachSelect(y, select) {
                            var $select = $(select);
                            var val = $select.find("option:selected").val();
                            output[$b.attr("data-builder")] += "{0}={1}&".format($select.attr("data-name"), val);
                        });
                    });

                    // Forward us to the new location
                    location.href = data.url + "?" + queryString.stringify(output);
                });

                $.each($("[data-default]"), function setupBuilderDefault(i, select) {
                    var $select = $(select),
                        defaultOpt = $select.find("[value='" + $select.attr("data-default") + "']");

                    defaultOpt.attr("selected", "selected");
                });

                selectors.init(); //TODO: Fix the bugs around this
            };

            function setupRealtime(index, data) {
                if (!$.isArray(data)) {
                    data = data.builders;
                }
                rawData[index] = data;
                $.each($tbBuilders, function eachBuilderTable(i) {
                    rtComparison.processBuilders(i);
                });
            }

            realtimeFunctions.builders0 = function realtimeBuilder0(data) {
                if ($tbBuilders[0] === undefined) {
                    $tbBuilders[0] = rtComparison.dataTableInit($('#builders0'));
                }
                setupRealtime(0, data);
            };
            realtimeFunctions.builders1 = function realtimeBuilder1(data) {
                if ($tbBuilders[1] === undefined) {
                    $tbBuilders[1] = rtComparison.dataTableInit($('#builders1'));
                }
                setupRealtime(1, data);
            };

            realtimePages.initRealtime(realtimeFunctions);
        },
        processBuildersData: function processBuildersData() {
            var SUCCESS = helpers.cssClassesEnum.SUCCESS,
                NOT_REBUILT = helpers.cssClassesEnum.NOT_REBUILT,
                DEPENDENCY_FAILURE = helpers.cssClassesEnum.DEPENDENCY_FAILURE,
                dataA = rawData[0],
                dataB = rawData[1],
                output = [
                    [],
                    []
                ];

            if (dataA !== undefined && dataB !== undefined) {

                // For each builder in dataA
                $.each(dataA, function eachBuilder(i, builderA) {

                    // Check that the other builder for differences
                    var builderB = dataB[i];
                    var diff = true;

                    if (builderA.latestBuild === undefined || builderB.latestBuild === undefined) {
                        diff = false;
                    } else {
                        if (builderA.latestBuild.number === builderB.latestBuild.number) {
                            diff = false;
                        } else {
                            var buildA = builderA.latestBuild,
                                buildB = builderB.latestBuild;

                            if (buildA.results !== undefined && buildB.results !== undefined) {
                                if (buildA.results === buildB.results) {
                                    if ((buildA.results === NOT_REBUILT || buildA.results === SUCCESS || buildA.results === DEPENDENCY_FAILURE)) {
                                        diff = false;
                                    }
                                } else if ((buildA.results === SUCCESS || buildA.results === NOT_REBUILT) && (buildB.results === SUCCESS || buildB.results === NOT_REBUILT)) {
                                    diff = false;
                                }
                            }
                        }
                    }

                    if (diff) {
                        $.each(rawData, function addBuilder(x, data) {
                            output[x].push(data[i]);
                        });
                    }
                });

            }

            return output;
        },
        processBuilders: function processBuilders(index) {
            if ($tbBuilders[index] !== undefined) {
                var data = rtComparison.processBuildersData()[index];
                rtTable.table.rtfGenericTableProcess($tbBuilders[index], data);

                //Update the height to the largest found
                var $elements = $(".comparison-table tr");
                var maxHeight = Math.max.apply(null, $elements.map(function () {
                    return $(this).height();
                }).get());
                $elements.css("height", maxHeight);
            }
        },
        dataTableInit: function dataTableInit($tableElem) {
            var options = {};

            options.aoColumns = [
                { "mData": null, "sWidth": "20%", "bSortable": false },
                { "mData": null, "sWidth": "10%", "sType": "number-ignore-zero", "bSortable": false },
                { "mData": null, "sWidth": "15%", "sType": "builder-status", "bSortable": false },
                { "mData": null, "sWidth": "5%", "bSortable": false }
            ];

            options.oLanguage = {
                "sEmptyTable": "No differences found or all builds were successful"
            };

            options.aoColumnDefs = [
                rtTable.cell.builderName(0, "txt-align-left"),
                rtTable.cell.buildLastRun(1),
                rtTable.cell.buildStatus(2, "latestBuild"),
                rtTable.cell.buildShortcuts(3, "latestBuild")
            ];

            return dt.initTable($tableElem, options);
        }
    };

    return rtComparison;
});