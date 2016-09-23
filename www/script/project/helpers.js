/*global define*/
define(function (require) {

    "use strict";
    var $ = require('jquery'),
        screenSize = require('screensize'),
        timeElements = require('timeElements'),
        moment = require('moment'),
        queryString = require("libs/query-string"),
        URI = require('libs/uri/URI');

    require('project/moment-extend');

    var helpers,
        css_class_enum = {},
        css_classes = {
            SUCCESS: [0, "success"],
            WARNINGS: [1, "warnings"],
            FAILURE: [2, "failure"],
            SKIPPED: [3, "skipped"],
            EXCEPTION: [4, "exception"],
            RETRY: [5, "retry"],
            CANCELED: [6, "exception"],
            NOT_REBUILT: [7, "not-rebuilt"],
            DEPENDENCY_FAILURE: [8, "dependency-failure"],
            RUNNING: [9, "running"],
            NOT_STARTED: [10, "not-started"],
            INTERRUPTED: [11, "interrupted"],
            None: ""
        },
        settings = {},
        key_codes = {
           ENTER : 13
        };

    $.each(css_classes, function (key, val) {
        css_class_enum[key] = val[0];
    });

    String.prototype.format = function () {
        var args = arguments;
        return this.replace(/\{(\d+)\}/g, function (match, number) {
            return args[number] !== undefined ? args[number] : match;
        });
    };

    Number.prototype.clamp = function (min, max) {
        return Math.min(Math.max(this, min), max);
    };

    helpers = {
        init: function () {
            // Set the currentmenu item
            helpers.setCurrentItem();

            if ($('#buildslave_page').length) {
                // display the number of current jobs
                helpers.displaySum($('#currentJobs'), $('#runningBuilds_onBuildslave').find('li'));
            }

            // submenu overflow on small screens
            helpers.menuItemWidth(screenSize.isMediumScreen());
            $(window).resize(function () {
                helpers.menuItemWidth(screenSize.isMediumScreen());
            });

            // chrome font problem fix
            $(function userAgent() {
                var is_chrome = /chrome/.test(navigator.userAgent.toLowerCase());
                var isFirefox = /firefox/.test(navigator.userAgent.toLowerCase());
                var isWindows = navigator.platform.toUpperCase().indexOf('WIN') !== -1;
                if (is_chrome) {
                    $('body').addClass('chrome');
                }
                if (isWindows) {
                    $('body').addClass('win');
                }

                if (isFirefox) {
                    $('body').addClass('firefox');
                }

            });

            // tooltip used on the builddetailpage
            helpers.toolTip('.ellipsis-js');

            // parse reason string on the buildqueue page
            helpers.parseReasonString();

            helpers.tooltip($('.tooltip'));

            helpers.initSettings();

        },
        randomImage: function (el) {
            var images = ['kitty-glasses.jpg'];
            el.attr('src', 'images/' + images[Math.floor(Math.random() * images.length)]);

        },
        tooltip: function (elements) {
            $.each(elements, function (i, el) {
                var $elem = $(el);

                if ($elem.hasClass('tipped')) {
                    return true;
                } else {
                    $elem.addClass('tipped');
                }

                var hoverIn = function (e) {
                    var title,
                        toolTipCont = $("<div/>").addClass("tooltip-cont"),
                        cursorPosTop = e.pageY + 20,
                        cursorPosLeft = e.pageX + 5;

                    if ($elem.attr("title") !== undefined) {
                        $elem.attr("data-title", $elem.attr("title"));
                        $elem.removeAttr("title");
                    }
                    title = $elem.attr("data-title");      

                    if (screenSize.isMediumScreen() || !$elem.hasClass('responsive-tooltip')) {
                        toolTipCont.html(title)
                            .appendTo('body')
                            .css({'top': cursorPosTop, 'left': cursorPosLeft})
                            .fadeIn('fast');
                    } else if ($elem.hasClass('responsive-tooltip')) {

                        toolTipCont.html(title)
                            .appendTo('body')
                            .css({'top': cursorPosTop, 'right': 28})
                            .fadeIn('fast');
                    }

                };

                var hoverOut = function () {                 
                    var fadeOut = function () {
                        $(this).unbind();
                        $(this).remove();
                    };
                    $('.tooltip-cont').fadeOut('fast', fadeOut);
                };

                $elem.hover(hoverIn, hoverOut);    
                $elem.bind('click.katana', hoverOut);    
            });
        },
        setCurrentItem: function () {

            var path = window.location.pathname.split("\/");

            $('.top-menu a').each(function (index) {
                var thishref = this.href.split("\/");

                if (this.id === path[1].trim().toLowerCase() || (this.id === 'home' && path[1].trim().toLowerCase().length === 0)) {
                    $(this).parent().addClass("selected");
                }
            });

        },
        jCenter: function ($el) {
            if ($el !== undefined && $el !== null) {

                var h = $(window).height();
                var w = $(window).width();
                var tu = $el.outerHeight();
                var tw = $el.outerWidth();

                // adjust height to browser height , "height":h - 75 , "height":'auto'

                if (h < (tu + 5)) {

                    $el.css({"top": 5 + $(window).scrollTop() + "px", "height": h - 60});
                } else {

                    $el.css({"top": (h - tu) / 2 + $(window).scrollTop() + 'px', "height": 'auto'});
                }

                $el.css("left", (w - tw) / 2 + $(window).scrollLeft() + "px");
                return $el;
            }
        },
        parseReasonString: function () { // parse reason string on the buildqueue page
            $('.codebases-list .reason-txt').each(function () {
                var rTxt = $(this).text().trim();
                if (rTxt === "A build was forced by '':") {
                    $(this).remove();
                }
            });

        },
        getInstantJSON: function () {
            return window.instantJSON;
        },
        selectBuildsAction: function ($table, dontUpdate, updateUrl, parameters, updateFunc) { // check all in tables and perform remove action

            if ($table === undefined) {
                $table = $('#tablesorterRt');
                if ($table.length === 0) {
                    return;
                }
            }
            var selectAll = $('#selectall');

            selectAll.bind("click.katana", function () {
                var tableNodes = $table.dataTable().fnGetNodes();
                $('.fi-js', tableNodes).prop('checked', this.checked);
            });

            function ajaxPost(str) {
                var $dataTable = $table.dataTable();
                $("#preloader").preloader("showPreloader");
                str = str + '&ajax=true';

                var json = helpers.getInstantJSON();
                if (json !== undefined && json.pending_builds && json.pending_builds.url) {
                    str = str + '&pending_builds_url=' + json.pending_builds.url;
                }

                $.ajax({
                    type: "POST",
                    url: updateUrl,
                    data: str,
                    success: function (data) {
                        //TODO: Remove this so that we can update with a URL that only returns
                        //the new ones
                        if (dontUpdate === false) {
                            updateFunc($dataTable, data);
                        }

                        selectAll.prop('checked', false);
                        $("#preloader").preloader("hidePreloader");
                    }
                });
                return false;
            }

            $('#submitBtn').bind("click.katana", function (e) {
                e.preventDefault();


                var $dataTable = $table.dataTable();
                var tableNodes = $dataTable.fnGetNodes();
                var checkedNodes = $('.fi-js', tableNodes);

                var formStr = "";
                checkedNodes.each(function () {
                    if ($(this).is(':checked')) {
                        formStr += parameters + $(this).val() + '&';
                    }
                });
                var formStringSliced = formStr.slice(0, -1);

                if (formStringSliced !== '') {
                    ajaxPost(formStringSliced);
                }
            });
            $table.delegate('.force-individual-js', 'click', function (e) {
                e.preventDefault();
                var iVal = $(this).prev().val();
                var str = parameters + iVal;
                ajaxPost(str);
            });

        },
        updateBuilders: function () {
            $.ajax({
                url: "/json/builders/?filter=0",
                dataType: "json",
                type: "GET",
                cache: false,
                success: function (data) {
                    var arrayBuilders = [];
                    var arrayPending = [];
                    var arrayCurrent = [];
                    $.each(data, function (key, value) {
                        arrayBuilders.push(key);
                        arrayPending.push(value.pendingBuilds);
                        if (value.state === 'building') {
                            arrayCurrent.push(value.currentBuilds);
                        }
                    });

                    function sumVal(arr) {
                        var sum = 0;
                        $.each(arr, function () {
                            sum += parseFloat(this) || 0;
                        });
                        return sum;
                    }

                    $('#pendingBuilds').text(sumVal(arrayPending));
                }
            });

            $.ajax({
                url: "/json/slaves/?filter=0",
                dataType: "json",
                type: "GET",
                cache: false,
                success: function (data) {
                    var arraySlaves = [];
                    $.each(data, function (key) {
                        arraySlaves.push(key);
                    });

                    $('#slavesNr').text(arraySlaves.length);
                }
            });
        },
        tableHeader: function (El, compareURL, tags) {
            var KT = require('precompiled.handlebars');

            if (El !== undefined && location.search.length > 0) {
                var args = queryString.parse(location.search),
                    branches = {compareURL: compareURL, codebases: []};

                // Fix up the data so it can be consumed by handlebars
                var count = 0;
                $.each(args, function (name, branch) {
                    if (name.indexOf("_branch") > -1) {
                        var cbName = name.replace("_branch", "");
                        branches.codebases[count] = {"codebase": cbName, "branch": branch};
                        count += 1;
                    }
                });

                // Create the table and append to the given element
                var cbTable = $(KT.partials.builders["builders:codebaseBranchesTable"](branches));
                cbTable.appendTo(El);
            }
            if (tags) {
                var $tagEl = $(KT.partials.builders["builders:tagsSelector"]({tags: tags, compareURL: compareURL}));
                $tagEl.prependTo(El);
            }
        },
        menuItemWidth: function (isMediumScreen) { // set the width on the breadcrumbnavigation. For responsive use

            if (isMediumScreen) {
                $('.breadcrumbs-nav').width('');
            } else {
                var wEl = 0;
                $('.breadcrumbs-nav li').each(function () {
                    wEl += $(this).outerWidth();
                });
                $('.breadcrumbs-nav').width(wEl + 100);
            }

        },
        toolTip: function (ellipsis) { // tooltip used on the builddetailpage
            $(ellipsis).parent().hover(function () {

                var txt = $(ellipsis, this).attr('data-txt');

                var toolTip = $('<div/>').addClass('tool-tip').text(txt);

                $(this).append($(toolTip).css({
                    'top': $(ellipsis, this).position().top - 10,
                    'left': $(ellipsis, this).position().left - 20
                }).show());

            }, function () {
                $('.tool-tip').remove();
            });
            // ios fix
            $(document).bind('click.katana touchstart.katana', function (e) {
                $('.tool-tip').remove();
                $(this).unbind(e);
            });
        },
        displaySum: function (displayEl, countEl) {
            // Insert the total length of the elements
            displayEl.text(countEl.length);

        },
        inDOM: function (element) {
            return $.contains(document.documentElement, element[0]);
        },
        delegateToProgressBar: function (bars) {
            $.each(bars, function (key, elem) {
                var obj = $(elem);
                timeElements.addProgressBarElem(obj, obj.attr('data-starttime'), obj.attr('data-etatime'));
            });
        },
        verticalProgressBar: function (el, per) {
            // must be replaced with json values
            el.height("{0}%".format(per));
        },
        getTime: function (start, end) {

            if (end === null) {
                end = Math.round(+new Date() / 1000);
            }

            var time = end - start;

            var getTime = Math.round(time);
            var days = Math.floor(time / 86400) === 0 ? '' : Math.floor(time / 86400) + ' days ';
            var hours = Math.floor(time / 3600) === 0 ? '' : Math.floor(time / 3600) % 24 + ' hours ';

            var minutes = Math.floor(getTime / 60) === 0 ? '' : Math.floor(getTime / 60) % 60 + ' mins, ';
            var seconds = getTime - Math.floor(getTime / 60) * 60 + ' secs ';
            return days + hours + minutes + seconds;

        },
        getResult: function (resultIndex) {

            var results = ["success", "warnings", "failure", "skipped", "exception", "retry", "canceled"];
            return results[resultIndex];

        },
        getSlavesResult: function (connected, runningBuilds) {

            return connected === false ? 'Not connected' : runningBuilds.length > 0 ? 'Running' : 'idle';

        },
        getClassName: function (connected, runningBuilds) {

            var slavesResult = helpers.getSlavesResult(connected, runningBuilds);

            return slavesResult === 'Not connected' ? 'status-td offline' : slavesResult === 'Running' ? 'status-td building' : 'status-td idle';

        },
        getCurrentPage: function () {
            // return the id of the page
            return document.getElementsByTagName('body')[0].id;
        },
        hasfinished: function () {
            var hasfinished = false;
            var isFinishedAttr = $('#isFinished').attr('data-isfinished');

            if (isFinishedAttr === undefined) {
                hasfinished = false;
            }

            if (isFinishedAttr === true) {
                hasfinished = true;
            }

            return hasfinished;

        },
        isRealTimePage: function () {
            var isRealtimePage = false;
            var currentRtPages = ['buildslaves_page', 'buildslavedetail_page', 'builderdetail_page', 'builddetail_page', 'buildqueue_page',
                'projects_page', 'home_page', 'builders_page', 'jsonhelp_page', 'usersettings_page'];
            var current = helpers.getCurrentPage();
            $.each(currentRtPages, function (key, value) {
                if (value === current) {
                    isRealtimePage = true;
                }
            });
            return isRealtimePage;

        },
        closePopup: function (boxElement, clearEl) {

            var closeBtn = $('.close-btn').add(document);

            closeBtn.bind('click.katana touchstart.katana', function (e) {

                if ((!$(e.target).closest(boxElement).length || $(e.target).closest('.close-btn').length)) {

                    if (clearEl === undefined) {
                        boxElement.remove();
                    } else {

                        boxElement.slideUp('fast', function () {
                            closeBtn.unbind(e);
                        });
                    }

                    closeBtn.unbind(e);

                }

            });
        },
        urlHasCodebases: function () {
            return Object.keys(helpers.codebasesFromURL({})).length > 0;
        },
        codebasesFromURL: function (urlParams) {
            var sPageURL = window.location.search.substring(1);
            var sURLVariables = sPageURL.split('&');
            $.each(sURLVariables, function (index, val) {
                var sParameterName = val.split('=');
                if (sParameterName[0].indexOf("_branch") >= 0) {
                    urlParams[sParameterName[0]] = sParameterName[1];
                }
            });

            return urlParams;
        },
        urlParamsToString: function (urlParams) {
            var ret = [];
            $.each(urlParams, function (name, value) {
                ret.push(name + "=" + value);
            });

            return ret.join("&");
        },
        getCssClassFromStatus: function (status) {
            var values = Object.keys(css_classes).map(function (key) {
                return css_classes[key];
            });
            return values[status][1];
        },
        setIFrameSize: function (iFrame) {
            if (iFrame) {
                var iFrameWin = iFrame.contentWindow || iFrame.contentDocument.parentWindow;
                if (iFrameWin.document.body) {
                    iFrame.height = iFrameWin.document.documentElement.scrollHeight || iFrameWin.document.body.scrollHeight;
                    iFrame.width = iFrameWin.document.documentElement.scrollWidth || iFrameWin.document.body.scrollWidth;
                }
            }
        },
        objectPropertiesToArray: function (arr) {
            var result = [],
                key;

            for (key in arr) {
                if (arr.hasOwnProperty(key)) {
                    result.push(arr[key]);
                }
            }

            return result;
        },
        debounce: function debounce(func, wait, immediate) {
            var timeout;
            return function () {
                var context = this, args = arguments;
                var later = function () {
                    timeout = null;
                    if (!immediate) func.apply(context, args);
                };
                var callNow = immediate && !timeout;
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
                if (callNow) func.apply(context, args);
            };
        },
        initSettings: function () {
            var script = $('#user-settings-json');
            if (script.length && window.userSettings !== undefined) {
                script.remove();
                settings = window.userSettings;
            }
            return undefined;
        },
        initRecentBuildsFilters: function initRecentBuildsFilters () {
            var args = URI.parseQuery(window.location.search);

            var tags = {
                results: [
                    {id: "0", text: "Success"},
                    {id: "1", text: "Warnings"},
                    {id: "2", text: "Failure"},
                    {id: "3", text: "Skipped"},
                    {id: "4", text: "Exception"},
                    {id: "5", text: "Retry"},
                    {id: "6", text: "Canceled"},
                    {id: "7", text: "Not Rebuilt"},
                    {id: "8", text: "Dependency Failure"}
                ]
            };

            var $buildResultSelector = $("#buildResultSelector"),
                $numBuildsSelector = $("#numBuildsSelector");

            $buildResultSelector.val(args.results).select2({"multiple": true,
                                                            "data": tags});

            // Set the value of the numBuildsSelector defaulting to 15 for when not found,
            // change location on change of the value and initialize select2
            $numBuildsSelector.val(args.numbuilds || 15).select2({minimumResultsForSearch: -1});

            $("#btnFilter").bind("click.katana", function changeNumBuilds() {
                var numBuilds = $numBuildsSelector.val();


                var url = URI(window.location.href).setQuery({numbuilds: numBuilds});

                var results_tags = $buildResultSelector.val();
                if (results_tags.length > 0) {
                    url.setQuery("results", results_tags.split(","));
                } else {
                    url.removeQuery("results");
                }

                window.location = url;
            });
        },
        isBuildOld: function isBuildOld(build) {
            var old_build_date = new Date();
            old_build_date.setDate(old_build_date.getDate() - helpers.settings().oldBuildDays);
            return (old_build_date.getTime() / 1000.0) > build.times[0];
        },
        /**
         * Clear all events and binding on the child elements,
         * this is super useful to make sure we don't have memory leaks
         * when DOM elements are removed from the DOM
         * @param $elem
         */
        clearChildEvents: function ($elem) {
            $elem.find("*").addBack().off(".katana");
        },
        cssClassesEnum: css_class_enum,
        settings: function getSettings() {
            return settings;
        },
        isLocalStorageQuotaExceeded: function (e) {
          var quotaExceeded = false;
          if (e) {
            if (e.code) {
              switch (e.code) {
                case 22:
                  quotaExceeded = true;
                  break;
                case 1014:
                  // Firefox
                  if (e.name === 'NS_ERROR_DOM_QUOTA_REACHED') {
                    quotaExceeded = true;
                  }
                break;
              }
            } else if (e.number === -2147024882) {
              // Internet Explorer 8
              quotaExceeded = true;
            }
          }
            return quotaExceeded;
        },
        getBuildersHistoryList: function (key) {
          var localStorage;
          try {
              localStorage = window.localStorage;
          } catch(e) {
              // Exception during access local storage
          }

          if(!localStorage) {
            return [];
          }
            
          var historyList = localStorage.getItem(key);

          return historyList ? JSON.parse(historyList) : [];
        },
        updateBuildersHistoryList: function (key, data) {
          var historyJson = JSON.stringify(data);
          try {
            localStorage.setItem(key, historyJson);
          } catch (e) {
            if(helpers.isLocalStorageQuotaExceeded(e)) {
              // Local storage is full, history item is going to be removed completely
              localStorage.removeItem(key);
            }
          }
        },
        history: function (element) {
          if(!element){
            return;
          }

          var historyElement = element;
          var historyItemLocalStorageKey = 'exthistorylist';
          var ext_history_list = helpers.getBuildersHistoryList(historyItemLocalStorageKey);

          if (location.pathname === '/') {
            if (ext_history_list.length) {
              $(historyElement)[0].innerHTML = "<h3 class='builders-list-header'>Recent projects:</h3><ul id='ext-history-list' class='builders-list'></ul>";
              var hist = $("#ext-history-list")[0];
              for (var i = 0; i < ext_history_list.length; i++) {
                var el = ext_history_list[i];
                var codebasesHtml = $("<div class='row branch-list'/>");
                $.each(el.codebases, function (i, val) {
                  if (val) {
                    $("<div class='branch-list-item'><div class='branch-icon'/> <span><strong>" + i.slice(0, -"_branch".length) + ": </strong>" + val + "</span></div>").appendTo(codebasesHtml);
                  }
                });
                
                var html = "<div class='row'><div class='col-md-8'><a class='builder-link' href='" + el.url + "'>" + unescape(el.proj) + "</a></div><div class='col-md-4'><span class='last-run'>"+ moment(el.time).fromNow()+"</span></div></div>";
                var listItem = $("<li />", {html: html});
                codebasesHtml.appendTo(listItem);
                listItem.appendTo(hist);
              }
            }
          }
          else {              
            var matches = location.href.match(new RegExp(/^.*\/projects\/([^\/]*)\/builders\?(.*)$/));
            if (matches && matches.length == 3) {
              var proj = matches[1];
              var url = location.href;
              var time = new Date();
              if (ext_history_list.length > 20) {
                ext_history_list.pop();
              }
              
              for (var j = 0; j < ext_history_list.length; j++) {
                if (ext_history_list[j].url == url) {
                  ext_history_list.splice(j, 1);
                  j--;
                }
              }
              
              ext_history_list.splice(0, 0, {proj: proj, codebases:this.codebasesFromURL({}), url: url, time: time});
              helpers.updateBuildersHistoryList(historyItemLocalStorageKey, ext_history_list);
            }
          }              
        },

        getPendingIcons: function (hb, data) {
            return hb.partials.cells["cells:pendingIcons"]({initial_queue: data.results !== 9});
        },

        getPriorityData: function (data, full){
            var priority = data.priority;
            if (full.properties !== undefined) {
                $.each(full.properties, function (i, prop) {
                    if (prop[0] === "selected_slave") {
                        priority += "<br/>" + prop[1];
                    }
                });
            }
            return priority;
        },
        keyCodes : key_codes
      };

    return helpers;
});
