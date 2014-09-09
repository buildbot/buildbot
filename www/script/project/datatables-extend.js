/*global define*/
define(['jquery', 'datatables', 'helpers', 'libs/natural-sort', 'ui.popup'], function ($, dataTable, helpers, naturalSort) {

    "use strict";
    var dataTables;

    dataTables = {
        init: function () {
            //Setup sort neutral function
            dataTables.initSortNatural();
            dataTables.initBuilderStatusSort();
            dataTables.initNumberIgnoreZeroSort();

            //Datatable Defaults
            $.extend($.fn.dataTable.defaults, {
                "bPaginate": false,
                "bLengthChange": false,
                "bFilter": false,
                "bSort": true,
                "bInfo": false,
                "bAutoWidth": false,
                "sDom": '<"table-wrapper"t>',
                "bRetrieve": true,
                "asSorting": true,
                "bServerSide": false,
                "bSearchable": true,
                "aaSorting": [],
                "iDisplayLength": 50,
                "bStateSave": true
            });

            $.extend($.fn.dataTable.defaults.oLanguage, {
                "sEmptyTable": "No data has been found"
            });
        },
        initTable: function ($tableElem, options) {

            var sDom = '<"top col-md-12"flip><"table-wrapper"t><"bottom"pi>';

            // add only filter input nor pagination
            if ($tableElem.hasClass('input-js')) {
                options.bFilter = true;
                options.oLanguage = {
                    "sSearch": ""
                };
                options.sDom = sDom;
            }

            // add searchfilterinput, length change and pagination
            if ($tableElem.hasClass('tools-js')) {
                options.bPaginate = true;
                options.bLengthChange = true;
                options.bInfo = true;
                options.bFilter = true;
                options.oLanguage = {
                    "sSearch": "",
                    "sLengthMenu": 'Entries per page<select>' +
                        '<option value="10">10</option>' +
                        '<option value="25">25</option>' +
                        '<option value="50">50</option>' +
                        '<option value="100">100</option>' +
                        '<option value="-1">All</option>' +
                        '</select>'
                };
                options.sDom = sDom;
            }

            //Setup default sorting columns and order
            var defaultSortCol;
            var sort = $tableElem.attr("data-default-sort-dir") || "asc";

            if ($tableElem.attr("data-default-sort-col") !== undefined) {
                defaultSortCol = parseInt($tableElem.attr("data-default-sort-col"), 10);
                options.aaSorting = [
                    [defaultSortCol, sort]
                ];
            }

            //Default sorting if not set
            var aoColumns = [];
            if (options.aoColumns === undefined) {

                $('> thead th', $tableElem).each(function (i, obj) {
                    if ($(obj).hasClass('no-tablesorter-js')) {
                        aoColumns.push({'bSortable': false });
                    } else if (defaultSortCol !== undefined && defaultSortCol === i) {
                        aoColumns.push({ "sType": "natural" });
                    } else {
                        aoColumns.push(null);
                    }
                });

                options.aoColumns = aoColumns;
            } else {
                aoColumns = options.aoColumns;

                $('> thead th', $tableElem).each(function (i, obj) {
                    if ($(obj).hasClass('no-tablesorter-js') && aoColumns[i].bSortable === undefined) {
                        aoColumns[i].bSortable = false;
                    } else if (aoColumns[i].bSortable === undefined) {
                        aoColumns[i].bSortable = true;
                    }

                    if (defaultSortCol !== undefined && defaultSortCol === i) {
                        aoColumns[i].sType = "natural";
                    }
                });

                options.aoColumns = aoColumns;
            }
            if ($tableElem.hasClass('branches-selectors-js') && options.sDom === undefined) {
                options.sDom = sDom;
            }

            //initialize datatable with options
            var oTable = $tableElem.dataTable(options);

            // Set the marquee in the input field on load and listen for key event

            var filterTableInput = $('.dataTables_filter input').attr('placeholder', 'Filter results');
            $('body').keyup(function (event) {
                if (event.which === 70) {
                    filterTableInput.focus();
                }
            });

            if (options.iFilterCol !== undefined) {
                dataTables.initSingleColumnFilter(options.iFilterCol);
            }

            return oTable;
        },
        initSortNatural: function () {
            //Add the ability to sort naturally
            $.extend($.fn.dataTableExt.oSort, {
                "natural-pre": function (a) {
                    if (typeof a === 'number') {
                        return a;
                    }
                    try {
                        a = $(a).text().trim();
                        return a;
                    } catch (err) {
                        return a;
                    }
                },
                "natural-asc": function (a, b) {
                    return naturalSort.sort(a, b);
                },

                "natural-desc": function (a, b) {
                    return naturalSort.sort(a, b) * -1;
                }
            });
        },
        initBuilderStatusSort: function () {
            var r = helpers.cssClassesEnum,
                priorityOrder = [r.FAILURE, r.DEPENDENCY_FAILURE, r.SUCCESS, r.NOT_REBUILT, r.CANCELED, r.RETRY, r.SKIPPED, r.EXCEPTION];

            var sort = function (a, b, reverse) {
                if (a.latestBuild !== undefined && b.latestBuild !== undefined) {
                    var aResult = a.latestBuild.results;
                    var bResult = b.latestBuild.results;

                    if (aResult === bResult) {
                        return 0;
                    }

                    var result = -1,
                        order = priorityOrder.slice();

                    if (reverse === true) {
                        order = order.reverse();
                    }

                    $.each(order, function (x, item) {
                        if (aResult === item) {
                            result = -1;
                            return false;
                        }

                        if (bResult === item) {
                            result = 1;
                            return false;
                        }

                        return true;
                    });


                    return result;
                }

                if (a.latestBuild === b.latestBuild) {
                    return 0;
                }
                if (a.latestBuild !== undefined) {
                    return -1;
                }

                return 1;
            };

            $.extend($.fn.dataTableExt.oSort, {
                "builder-status-asc": function (a, b) {
                    return sort(a, b, false);
                },
                "builder-status-desc": function (a, b) {
                    return sort(a, b, true);
                }
            });
        },
        initNumberIgnoreZeroSort: function initNumberSortMinusZero() {
            var sort = function sort(a, b, reverse) {
                var result = -1;

                if (a === b) {
                    return 0;
                }

                // Push 0 results always to the bottom
                if (a === 0) {
                    return 1;
                }
                if (b === 0) {
                    return -1;
                }

                //Sort with normal numbers but allow for reversal
                if (a > b) {
                    result = 1;
                } else {
                    result = -1;
                }

                if (reverse) {
                    return -result;
                }

                return result;
            };

            $.extend($.fn.dataTableExt.oSort, {
                "number-ignore-zero-asc": function (a, b) {
                    return sort(a, b, false);
                },
                "number-ignore-zero-desc": function (a, b) {
                    return sort(a, b, true);
                }
            });
        },
        initSingleColumnFilter: function initSingleColumnFilter(index) {
            $.fn.dataTableExt.afnFiltering.push(
                function filter(oSettings, aData, iDataIndex) {
                    var f = oSettings.oPreviousSearch.sSearch;
                    if (f !== undefined && f.length > 0) {
                        var regex = new RegExp(f, "i"),
                            text = $(aData[index]).text();

                        // Attempt converting the HTML before using the plain string
                        if (text.length === 0) {
                            text = aData[index];
                        }
                        return text.search(regex) > -1;
                    }
                    return true;
                }
            );
        }
    };

    return dataTables;
});
