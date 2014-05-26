/*global define, requirejs*/
define(['jquery', 'helpers', 'libs/jquery.form', 'text!templates/popups.mustache', 'mustache', 'timeElements'], function ($, helpers, form, popups, Mustache, timeElements) {

    "use strict";
    var popup;

    popup = {
        init: function () {

            //For non ajax boxes
            var $tableSorterRt = $('#tablesorterRt');
            popup.registerJSONPopup($tableSorterRt);

            $('.popup-btn-js-2').click(function (e) {
                e.preventDefault();
                popup.nonAjaxPopup($(this));
            });

            $tableSorterRt.delegate('.popup-btn-js', 'click', function (e) {
                e.preventDefault();
                var currentUrl = document.URL;
                var parser = document.createElement('a');
                parser.href = currentUrl;
                var builder_name = encodeURIComponent($(this).attr('data-builderName'));
                var url = "{0}//{1}/json/pending/{2}/?".format(parser.protocol, parser.host, builder_name);
                var urlParams = helpers.codebasesFromURL({});
                var paramsString = helpers.urlParamsToString(urlParams);

                popup.pendingJobs(url + paramsString);
            });

            // Display the codebases form in a popup
            $('#getBtn').click(function (e) {
                e.preventDefault();
                popup.codebasesBranches();
            });

            // popbox for ajaxcontent
            $tableSorterRt.delegate('.ajaxbtn', 'click', function (e) {
                e.preventDefault();
                popup.externalContentPopup($(this));
            });

            $('.ajaxbtn').click(function (e) {
                e.preventDefault();
                popup.externalContentPopup($(this));
            });

        }, showjsonPopup: function (jsonObj) {
            var mustacheTmpl = Mustache.render(popups, jsonObj);
            var mustacheTmplShell = $(Mustache.render(popups, {MoreInfoBoxOuter: true}, {partial: mustacheTmpl}));

            $('body').append(mustacheTmplShell);

            if (jsonObj.showRunningBuilds != undefined) {
                helpers.delegateToProgressBar($('div.more-info-box-js div.percent-outer-js'));
            }

            helpers.jCenter(mustacheTmplShell).fadeIn('fast', function () {
                helpers.closePopup(mustacheTmplShell);
            });

        }, validateForm: function (formContainer) { // validate the forcebuildform
            var formEl = $('.command_forcebuild', formContainer);
            var excludeFields = ':button, :hidden, :checkbox, :submit';
            $('.grey-btn', formEl).click(function (e) {

                var allInputs = $('input', formEl).not(excludeFields);

                var rev = allInputs.filter(function () {
                    return this.name.indexOf("revision") >= 0;
                });

                var emptyRev = rev.filter(function () {
                    return this.value === "";
                });

                if (emptyRev.length > 0 && emptyRev.length < rev.length) {

                    rev.each(function () {
                        if ($(this).val() === "") {
                            $(this).addClass('not-valid');
                        } else {
                            $(this).removeClass('not-valid');
                        }
                    });

                    $('.form-message', formEl).hide();

                    if (!$('.error-input', formEl).length) {
                        var mustacheTmplErrorinput = Mustache.render(popups, {'errorinput': 'true', 'text': 'Fill out the empty revision fields or clear all before submitting'});
                        var errorinput = $(mustacheTmplErrorinput);
                        $(formEl).prepend(errorinput);
                    }
                    e.preventDefault();
                }
            });
        }, nonAjaxPopup: function (thisEl) {
            var clonedInfoBox = thisEl.next($('.more-info-box-js')).clone();
            clonedInfoBox.appendTo($('body'));
            helpers.jCenter(clonedInfoBox).fadeIn('fast', function () {
                helpers.closePopup(clonedInfoBox);
            });
            $(window).resize(function () {
                helpers.jCenter(clonedInfoBox);
            });

        },
        pendingJobs: function (url) {
            var mustacheTmpl = Mustache.render(popups, {'preloader': 'true'});
            var preloader = $(mustacheTmpl);

            $('body').append(preloader).show();

            $.ajax({
                url: url,
                cache: false,
                dataType: "json",

                success: function (data) {
                    preloader.remove();
                    var mustacheTmpl = Mustache.render(popups, {pendingJobs: data, showPendingJobs: true, cancelAllbuilderURL: data[0].builderURL});
                    var mustacheTmplShell = $(Mustache.render(popups, {MoreInfoBoxOuter: true}, {partial: mustacheTmpl}));
                    var waitingtime = mustacheTmplShell.find('.waiting-time-js');
                    waitingtime.each(function (i) {
                        timeElements.addElapsedElem($(this), data[i].submittedAt);
                        timeElements.updateTimeObjects();
                    });

                    mustacheTmplShell.find('form').ajaxForm({
                        success: function (data, text, xhr, $form) {
                            requirejs(['realtimePages'], function (realtimePages) {
                                setTimeout(function () {
                                    var name = "builders";
                                    realtimePages.updateSingleRealTimeData(name, data);
                                }, 300);
                            });

                            var cancelAll = $form.attr("id") === "cancelall";
                            if (cancelAll) {
                                $form.parent().remove();

                            }

                            if (cancelAll || mustacheTmplShell.find('li').length === 1) {
                                mustacheTmplShell.remove();
                            }
                        }
                    });

                    mustacheTmplShell.appendTo('body');
                    helpers.jCenter(mustacheTmplShell).fadeIn('fast', function () {
                        helpers.closePopup(mustacheTmplShell);
                    });
                }
            });
        }, codebasesBranches: function () {

            var path = $('#pathToCodeBases').attr('href');

            var mustacheTmpl = Mustache.render(popups, {'preloader': 'true'});
            var preloader = $(mustacheTmpl);

            $('body').append(preloader).show();
            var mib = popup.htmlModule('Select branches');

            $(mib).appendTo('body');


            $.get(path)
                .done(function (data) {
                    require(['selectors'], function (selectors) {

                        var formContainer = $('#content1');
                        preloader.remove();

                        var fw = $(data).find('#formWrapper');
                        fw.children('#getForm').attr('action', window.location.href);
                        var blueBtn = fw.find('.blue-btn[type="submit"]').val('Update');


                        fw.appendTo(formContainer);

                        helpers.jCenter(mib).fadeIn('fast', function () {
                            selectors.init();
                            blueBtn.focus();
                            helpers.closePopup(mib);

                        });

                        $(window).resize(function () {
                            helpers.jCenter(mib);
                        });

                    });
                });
        },
        customTabs: function () { // tab list for custom build
            $('.tabs-list li').click(function (i) {
                var indexLi = $(this).index();
                $(this).parent().find('li').removeClass('selected');
                $(this).addClass('selected');
                $('.content-blocks > div').each(function (i) {
                    if ($(this).index() != indexLi) {
                        $(this).hide();
                    } else {
                        $(this).show();
                    }
                });

            });
        }, externalContentPopup: function (thisEl) { // custom buildpopup on builder and builders
            var popupTitle = '<h2 class="small-head">' + thisEl.attr('data-popuptitle') + '</h2>';
            var datab = thisEl.attr('data-b');
            var dataindexb = thisEl.attr('data-indexb');
            var dataReturnPage = thisEl.attr('data-returnpage');
            var rtUpdate = thisEl.attr('data-rt_update');
            var contentType = thisEl.attr('data-contenttype');
            var builder_name = thisEl.attr('data-b_name');
            var mustacheTmpl = Mustache.render(popups, {'preloader': 'true'});
            var preloader = $(mustacheTmpl);

            var mustacheTmplTxt = '<h2 class="small-head">Your build will show up soon</h2>';
            var mustacheTmplShell = $(Mustache.render(popups, {MoreInfoBoxOuter: true, popUpClass: 'green'}, {partial: mustacheTmplTxt}));

            var body = $('body');
            body.append(preloader);

            var mustacheTmplMib = $(Mustache.render(popups, {MoreInfoBoxOuter: true}, {partial: popupTitle}));

            mustacheTmplMib.append($('<div id="content1"></div>')).appendTo(body);

            //get all branches
            var urlParams = {rt_update: rtUpdate, datab: datab, dataindexb: dataindexb, builder_name: builder_name, returnpage: dataReturnPage};
            var sPageURL = window.location.search.substring(1);
            var sURLVariables = sPageURL.split('&');
            $.each(sURLVariables, function (index, val) {
                var sParameterName = val.split('=');
                if (sParameterName[0].indexOf("_branch") >= 0) {
                    urlParams[sParameterName[0]] = sParameterName[1];
                }
            });

            // get currentpage with url parameters
            var url = location.protocol + "//" + location.host + "/forms/forceBuild";
            $.get(url, urlParams).done(function (data) {
                var exContent = $('#content1');
                preloader.remove();
                $(data).appendTo(exContent);

                helpers.tooltip(exContent.find($('.tooltip')));
                // Insert full name from cookie
                if (contentType === 'form') {
                    popup.validateForm(exContent);
                }

                helpers.jCenter(mustacheTmplMib).fadeIn('fast');
                $(window).resize(function () {
                    helpers.jCenter(mustacheTmplMib);
                });
                // popup.customTabs();
                helpers.closePopup(mustacheTmplMib);

                if (dataReturnPage !== undefined) {
                    exContent.find('form').ajaxForm({
                        beforeSubmit: function () {
                            body.append(mustacheTmplShell);

                            helpers.jCenter(mustacheTmplShell).fadeIn('fast', function () {
                                helpers.closePopup($(this));
                                $(this).delay(1500).fadeOut('fast', function () {
                                    $(this).remove();
                                });
                            });

                            exContent.closest('.more-info-box').find('.close-btn').click();
                        },
                        success: function (data) {
                            requirejs(['realtimePages'], function (realtimePages) {
                                mustacheTmplShell.remove();
                                var name = dataReturnPage.replace("_json", "");
                                realtimePages.updateSingleRealTimeData(name, data);
                            });
                        }
                    });
                }
            });

        }, htmlModule: function (headLine) { // html chunks
            var mib =
                $('<div class="more-info-box remove-js">' +
                    '<span class="close-btn"></span>' +
                    '<h3 class="codebases-head">' + headLine + '</h3>' +
                    '<div id="content1"></div></div>');

            return mib;
        },
        registerJSONPopup: function ($parentElem) {
            $parentElem.delegate('a.popup-btn-json-js', 'click', function (e) {
                e.preventDefault();
                popup.showjsonPopup($(this).data());
                timeElements.updateTimeObjects();
            });
        }
    };
    return popup;
});
