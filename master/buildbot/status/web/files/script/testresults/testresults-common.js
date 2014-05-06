/*global define, jQuery */
define(['jquery', 'moment', 'helpers', 'datatables-plugin'], function ($, moment, helpers) {

    "use strict";
    var oTable,
        th,
        privateFunc = {
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
                        anControl.unbind('keyup').bind('keypress', function (e) {
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
                $('.new-window').click(function (e) {
                    e.preventDefault();
                    var newWinHtml = $(this).parent().find($('.failure-detail-txt')).html();
                    privateFunc.openNewWindow(newWinHtml);
                });

                // show more / hide
                $('.height-toggle').click(function (e) {
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
            parseTimes: function () {
                $.each($("[data-time]"), function (i, elem) {
                    var ms = parseFloat($(elem).attr("data-time")) * 1000.0,
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

                $submitButton.click(function () {
                    privateFunc.filterTables($filterInput.val());
                });

                // clear the input field
                $('#clearFilter').click(function () {
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
                var $dtWTop = $('.top');
                if (window.location.search !== '') {
                    // Parse the url and insert current codebases and branches
                    helpers.codeBaseBranchOverview($dtWTop);
                }
            }
        },
        publicFunc = {
            init: function () {

                th = $('.table-holder');
                privateFunc.dataTablesInit();
                privateFunc.parseTimes();
                privateFunc.setupFilterButtons();
                privateFunc.addCodebasesBar();

                var checkboxesList = $('#CheckBoxesList').find('input');
                checkboxesList.click(function () {
                    privateFunc.filterCheckboxes();
                });
                privateFunc.filterCheckboxes();

                setTimeout(privateFunc.addFailureButtons, 100);
            }
        };

    $(document).ready(function () {
        publicFunc.init();
    });

    return publicFunc;
});
