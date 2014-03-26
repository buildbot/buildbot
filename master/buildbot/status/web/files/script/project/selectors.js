define(['select2'], function () {

    "use strict";
    var selectors;

    selectors = {

        //Set the highest with on both selectors
        init: function () {
            
            var selectBranches = $(".select-tools-js");
            var commonbranchSelect = $("#commonBranch_select");

            selectBranches.select2({
                width: selectors.getMaxChildWidth(selectBranches),
                minimumResultsForSearch: 10
            });

            // invoke the sortingfunctionality when the selector
            selectBranches.add(commonbranchSelect).on("select2-open", function () {
                selectors.clickSort();
            });

            // fill the options in the combobox with common options
            selectors.comboBox(selectBranches, commonbranchSelect);

            //Invoke select2 for the common selector
            commonbranchSelect.select2({
                width: selectors.getMaxChildWidth(commonbranchSelect),
                placeholder: "Select a branch"
            });

            // unbind the click event on close for the sorting functionality
            commonbranchSelect.add(selectBranches).on("select2-close", function () {
                $('.sort-name').unbind('click');
                $('.select2-container').removeClass('select2-container-active');
            });

            selectBranches.on("select2-selecting", function () {
                commonbranchSelect.select2("val", "");
            });


        }, getMaxChildWidth: function (sel) {
            var max = 80;

            sel.each(function () {
                var c_width = $(this).width();

                if (c_width > max) {
                    max = c_width + 30;
                }
            });

            return max;
        },
        // combobox on codebases
        comboBox: function (selector, commonbranchSelect) {

            // Find common options
            $('option', selector).each(function () {
                $(this).clone().prop('selected', false).appendTo(commonbranchSelect)
            });
            
            // remove the duplicates
            var removedDuplicatesOptions = {};
            $('option', commonbranchSelect).each(function () {
                var value = $(this).text();
                if (removedDuplicatesOptions[value] == null) {
                    removedDuplicatesOptions[value] = true;
                } else {
                    $(this).remove();
                }
            });

            var defaults = [];
            $(selector).each(function (i, obj) {
                var opt = $('option[selected]', obj);
                defaults.push(opt.html().trim())
            });

            commonbranchSelect.on("change", function () {
                var commonVal = $(this);
                $(selector).each(function (i, obj) {
                    $('option', obj).each(function () {
                        if ($(this).val() === $(commonVal).val()) {
                            $(this).parent().children('option').prop('selected', false);
                            $(this).prop('selected', true);
                            return false;
                        }
                        return true;
                    });

                    if ($(obj).val() !== commonVal.val()) {
                        $(obj).val(defaults[i]);
                    }
                });

                selector.trigger("change");
            });

        },
        // sort selector list by name
        clickSort: function () {
            var selector = $('#select2-drop');
            var selectResults = selector.children(".select2-results");
            var sortLink = selector.children('.sort-name');

            sortLink.bind('click', function (e) {
                e.preventDefault();
                sortLink.toggleClass('direction-up');
                selectResults.children('li').sort(function (a, b) {
                    var upA = $(a).text().toUpperCase();
                    var upB = $(b).text().toUpperCase();
                    if (!sortLink.hasClass('direction-up')) {
                        return (upA < upB) ? -1 : (upA > upB) ? 1 : 0;
                    } else {
                        return (upA > upB) ? -1 : (upA < upB) ? 1 : 0;
                    }
                }).appendTo(selectResults);
                selectResults.prop({ scrollTop: 0 });
            });
        }
    };

    return selectors;
});