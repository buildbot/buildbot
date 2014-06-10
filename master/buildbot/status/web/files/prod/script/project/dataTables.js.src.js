/*global define*/
define(['jquery', 'datatables-plugin', 'helpers', 'libs/natural-sort', 'popup'], function ($, dataTable, helpers, naturalSort) {

    
    var dataTables;

    dataTables = {
        init: function () {
            //Setup sort neutral function
            dataTables.initSortNatural();
            dataTables.initBuilderStatusSort();

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
        },
        initTable: function ($tableElem, options) {

            // add only filter input nor pagination
            if ($tableElem.hasClass('input-js')) {
                options.bFilter = true;
                options.oLanguage = {
                    "sSearch": ""
                };
                options.sDom = '<"top"flip><"table-wrapper"t><"bottom"pi>';
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
                options.sDom = '<"top"flip><"table-wrapper"t><"bottom"pi>';
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
                options.sDom = '<"top"flip><"table-wrapper"t><"bottom"pi>';
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
                priorityOrder = [r.FAILURE, r.DEPENDENCY_FAILURE, r.SUCCESS, r.NOT_REBUILT, r.EXCEPTION];

            var sort = function (a, b) {
                    if (a.latestBuild !== undefined && b.latestBuild !== undefined) {
                        var  aResult = a.latestBuild.results;
                        var  bResult = b.latestBuild.results;

                        if (aResult === bResult) {
                            return 0;
                        }

                        var result = -1;
                        $.each(priorityOrder, function (x, item) {
                            if (aResult === item) {
                                result =  -1;
                                return false;
                            }

                            if (bResult === item) {
                                result =  1;
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
                    return sort(a, b);
                },
                "builder-status-desc": function (a, b) {
                    return sort(a, b) * -1;
                }
            });
        }
    };

    return dataTables;
});
