/*global define, jQuery, require */
define(function (require) {
    "use strict";

    var $ = require('jquery'),
        helpers = require('helpers'),
        moment = require('moment'),
        oTable,
        th,
        rtTestReport,
        realtimeRouting = require('realtimerouting');


    rtTestReport = {
        init: function () {
            th = $('.table-holder');
            rtTestReport.dataTablesInit();
            rtTestReport.parseTimes("[data-time]");
            rtTestReport.setupFilterButtons();
            rtTestReport.addCodebasesBar();

            var checkboxesList = $('#CheckBoxesList').find('input');
            checkboxesList.bind("click.katana", function () {
                rtTestReport.filterCheckboxes();
            });
            rtTestReport.filterCheckboxes();
            helpers.initRecentBuildsFilters();

            setTimeout(rtTestReport.addFailureButtons, 100);
        },
        dataTablesInit: function () {
            //Filter tables based on checkboxes
            $.fn.dataTableExt.oApi.fnFilterAll = function (oSettings, sInput, iColumn, bRegex, bSmart) {
                var settings = $.fn.dataTableSettings,
                    i;

                for (i = 0; i < settings.length; i += 1) {
                    settings[i].oInstance.fnFilter(sInput, iColumn, bRegex, bSmart);
                }

                $('.dataTables_empty').closest(th).hide();
            };

            //Filter when return is hit
            jQuery.fn.dataTableExt.oApi.fnFilterOnReturn = function () {
                var that = this;

                this.each(function (i) {
                    $.fn.dataTableExt.iApiIndex = i;
                    var anControl = $('input', that.fnSettings().aanFeatures.f);
                    anControl.unbind('keyup').bind('keypress.katana', function (e) {
                        if (e.which === 13) {
                            $.fn.dataTableExt.iApiIndex = i;
                            that.fnFilter(anControl.val());
                        }
                    });
                    return this;
                });
                return this;
            };

            //Setup all datatables
            oTable = $('.tablesorter-log-js').dataTable({
                "asSorting": false,
                "bPaginate": false,
                "bFilter": true,
                "bSort": false,
                "bInfo": false,
                "bAutoWidth": false
            });

            $('a.collapse').click(function () {
                var target = $(this).attr('data-target');
                var hidden = $(target).is(":hidden");
                $(target).toggle(hidden);
            });
        },
        addFailureButtons: function () {
            $('.failure-detail-cont', th).each(function () {
                var $fdTxt = $('.failure-detail-txt', this);
                $fdTxt.text($fdTxt.text().trim());
                $(this).height($fdTxt.height() + 40);

                if (!$fdTxt.is(':empty')) {
                    $('<a href="#" class="new-window var-3 grey-btn">Open new window</a>').insertBefore($fdTxt);
                    if ($fdTxt.height() >= 130) {
                        $('<a class="height-toggle var-3 grey-btn" href="#">Show more</a>').insertBefore($fdTxt);
                    }
                }

            });

            // show content of exceptions in new window
            $('.new-window').bind("click.katana", function (e) {
                e.preventDefault();
                var newWinHtml = $(this).parent().find($('.failure-detail-txt')).html();
                privateFunc.openNewWindow(newWinHtml);
            });

            // show more / hide
            $('.height-toggle').bind("click.katana", function (e) {
                e.preventDefault();
                var $failDetail = $(this).parent().find($('.failure-detail-txt')),
                    parentTd = $(this).parent().parent();

                $failDetail.css({'max-height': 'none', 'height': ''});

                if (!$(this).hasClass('expanded-js')) {
                    $(this).addClass('expanded-js');
                    $(this).text('Show less');
                    $failDetail.css('height', '');
                    parentTd.css('height', $failDetail.height() + 40);
                } else {
                    $(this).removeClass('expanded-js');
                    $(this).text('Show more');
                    $failDetail.css('max-height', 130);
                    parentTd.css('height', 170);
                }
            });
        },
        parseTimes: function (elements) {
            $.each($(elements), function (i, elem) {
                var timeUnit = $(elem).attr("data-time-unit");
                var msUnit = timeUnit && timeUnit.trim().toLowerCase() === "ms";
                var ms = parseFloat($(elem).attr("data-time")) * (msUnit ? 1 : 1000.0),
                    parsedTime = moment.utc(ms).format(" (HH:mm:ss)");
                $(elem).append(parsedTime);
            });
        },
        filterCheckboxes: function () {
            var iFields = $('#CheckBoxesList').find('input:checked'),
                checkString = [];
            th.show();

            iFields.each(function () {
                checkString.push('(' + $(this).val() + ')');
            });
            oTable.fnFilterAll(checkString.join("|"), 1, true);
        },
        setupFilterButtons: function () {
            // submit on return
            var $filterInput = $("#filterinput"),
                $submitButton = $('#submitFilter'),
                failedTests = $(".log-main").attr("data-failed-tests");

            $filterInput.keydown(function (event) {
                // Filter on the column (the index) of this element
                var e = window.event || event;
                if (e.keyCode === 13) {
                    privateFunc.filterTables(this.value);
                }
            });

            $submitButton.bind("click.katana", function () {
                privateFunc.filterTables($filterInput.val());
            });

            // clear the input field
            $('#clearFilter').bind("click.katana", function () {
                $filterInput.val("");
                $submitButton.click();
            });

            if (failedTests === 0) {
                $("#failedinput").attr("checked", false);
                $("#passinput").attr("checked", true);
            }
        },
        filterTables: function (inputVal, num, bool) {
            th.show(inputVal);
            oTable.fnFilterAll(inputVal, num, bool);
        },
        openNewWindow: function (html) {
            var w = window.open();

            html = "<style>body {padding:0 0 0 15px;margin:0;" +
                "font-family:'Courier New';font-size:12px;white-space:" +
                " pre;overflow:auto;}</style>" + html;

            $(w.document.body).html(html);
        },
        addCodebasesBar: function () {
            // insert codebase and branch on the builders page
            helpers.tableHeader($('.top'));
        }
    };

    realtimeRouting.addPageInitHandler("testresults_page",function () {
        rtTestReport.init();
    });

    return rtTestReport;
});
