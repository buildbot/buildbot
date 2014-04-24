define(['jquery', 'moment', 'datatables-plugin'], function ($, moment) {

    "use strict";

    var oTable = undefined;
    var th = undefined;

    var testResults = {
        init: function () {

            th = $('.table-holder');
            testResults._dataTablesInit();
            testResults._parseTimes();
            testResults._setupFilterButtons();

            var checkboxesList = $('#CheckBoxesList').find('input');
            checkboxesList.click(function () {
                testResults._filterCheckboxes();
            });
            testResults._filterCheckboxes();

            setTimeout(testResults._addFailureButtons, 100);
        },
        _dataTablesInit: function () {
            //Filter tables based on checkboxes??!?!?! TODO
            $.fn.dataTableExt.oApi.fnFilterAll = function (oSettings, sInput, iColumn, bRegex, bSmart) {
                var settings = $.fn.dataTableSettings;

                for (var i = 0; i < settings.length; i++) {
                    settings[i].oInstance.fnFilter(sInput, iColumn, bRegex, bSmart);
                }

                var dv = $('.dataTables_empty').closest(th);
                $(dv).hide();
            };

            //Filter when return is hit
            jQuery.fn.dataTableExt.oApi.fnFilterOnReturn = function() {
                var _that = this;

                this.each(function (i) {
                    $.fn.dataTableExt.iApiIndex = i;
                    var anControl = $('input', _that.fnSettings().aanFeatures.f);
                    anControl.unbind('keyup').bind('keypress', function (e) {
                        if (e.which == 13) {
                            $.fn.dataTableExt.iApiIndex = i;
                            _that.fnFilter(anControl.val());
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
        _addFailureButtons: function () {
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
                testResults._openNewWindow(newWinHtml);
            });

            // show more / hide
            $('.height-toggle').click(function (e) {
                e.preventDefault();
                var $failDetail = $(this).parent().find($('.failure-detail-txt'));
                var parentTd = $(this).parent().parent();

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
        _parseTimes: function () {
            $.each($("[data-time]"), function (i, elem) {
                var ms = parseFloat($(elem).attr("data-time")) * 1000.0;
                var parsedTime = moment.utc(ms).format(" (HH:mm:ss)");
                $(elem).append(parsedTime);
            });
        },
        _filterCheckboxes: function () {
            var iFields = $('#CheckBoxesList').find('input:checked'),
                checkString = [];
            th.show();

            iFields.each(function () {
                checkString.push('(' + $(this).val() + ')');
            });
            oTable.fnFilterAll(checkString.join("|"), 1, true);
        },
        _setupFilterButtons: function () {
            // submit on return
            var $filterInput = $("#filterinput");
            var $submitButton = $('#submitFilter');
            $filterInput.keydown(function (event) {
                // Filter on the column (the index) of this element
                var e = (window.event) ? window.event : event;
                if (e.keyCode == 13) {
                    testResults._filterTables(this.value);
                }
            });

            $submitButton.click(function () {
                testResults._filterTables($filterInput.val());
            });

            // clear the input field
            $('#clearFilter').click(function () {
                $filterInput.val("");
                $submitButton.click();
            });
        },
        _filterTables: function (inputVal, num, bool) {
            th.show(inputVal);
            oTable.fnFilterAll(inputVal, num, bool);
        },
        _openNewWindow: function (html) {
            var w = window.open();

            html = "<style>body {padding:0 0 0 15px;margin:0;" +
                "font-family:'Courier New';font-size:12px;white-space:" +
                " pre;overflow:auto;}</style>" + html;

            $(w.document.body).html(html);
        }
    };

    $(document).ready(function () {
        testResults.init();


        // remove empty tds for rows with colspan
        //$('.colspan-js').nextAll('td').remove();


    });
});
