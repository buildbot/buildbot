/*global define, Handlebars */
define(['jquery', 'realtimePages', 'helpers', 'handlebars', 'mustache', 'text!templates/build.handlebars', 'text!templates/builders.mustache', 'timeElements', 'popup'], function ($, realtimePages, helpers, hb, mustache, build, builders, timeElements, popups) {
    
    var rtBuildDetail,
        buildHandle = Handlebars.compile(build),
        isLoaded = false,
        noMoreReloads = false;

    //Global helper for Handlebar
    //TODO: Move this when it's used by more pages
    Handlebars.registerHelper('buildCSSClass', function (value) {
        return helpers.getCssClassFromStatus(value);
    });

    var privFunc = {
        updateArtifacts: function (data) { // for the builddetailpage. Puts the artifacts and testresuts on top
            var $artifactsJSElem = $("#artifacts-js").empty(),
                artifactsDict = {},
                testLogsDict = {},
                html;

            /*jslint unparam: true*/
            $.each(data.steps, function (i, obj) {
                if (obj.urls !== undefined) {
                    $.each(obj.urls, function (name, url) {
                        if (typeof url === "string") {
                            artifactsDict[name] = url;
                        }
                    });
                }
            });

            $.each(data.logs, function (i, obj) {
                if (obj.length === 2 && (obj[1].indexOf(".xml") > -1 || obj[1].indexOf(".html") > -1)) {
                    testLogsDict[obj[0]] = obj[1];
                }
            });
            /*jslint unparam: false*/

            if (artifactsDict === undefined || Object.keys(artifactsDict).length === 0) {
                $artifactsJSElem.html("No artifacts");
            } else {
                html = '<a class="artifact-popup artifacts-js more-info" href="#">Artifacts ({0})&nbsp;</a>'.format(Object.keys(artifactsDict).length);
                $artifactsJSElem.html(html);

                popups.initArtifacts(artifactsDict, $artifactsJSElem.find(".artifact-popup"));
            }

            if (Object.keys(testLogsDict).length > 0) {
                html = '<li>Test Results</li>';

                $.each(testLogsDict, function (url, name) {
                    html += '<li class="s-logs-js"><a href="{0}">{1}</a></li>'.format(name, url);
                });

                html = $("<ul/>").addClass("tests-summary-list list-unstyled").html(html);

                $artifactsJSElem.append(html);
            }
        }
    };

    rtBuildDetail = {
        init: function () {
            var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
            realtimeFunctions.build = rtBuildDetail.processBuildDetailPage;
            realtimePages.initRealtime(realtimeFunctions);
            timeElements.setHeartbeat(1000);

            // insert codebase and branch on the builders page
            if (window.location.search !== '') {
                // Parse the url and insert current codebases and branches
                var $dtWTop = $('.top');
                helpers.codeBaseBranchOverview($dtWTop);
            }

            //Allow for popups
            $(".popup-btn-js-2").click(function (e) {
                e.preventDefault();
                var $elem = $(e.target);
                var html = $elem.next(".more-info-box-js").html(),
                    $body = $("body"),
                    $popup = $("<div/>").popup({
                        title: "",
                        html: html,
                        destroyAfter: true
                    });

                $body.append($popup);
            });
        },
        processBuildDetailPage: function (data) {
            //We get slighlty different data objects from autobahn
            var keys = Object.keys(data);
            if (keys.length === 1) {
                data = data[keys[0]];
            }

            var buildStartTime = data.times[0],
                buildEndTime = data.times[1],
                buildFinished = (buildEndTime !== null),
                eta = data.eta;

            rtBuildDetail.refreshIfRequired(buildFinished);

            //Process Page
            rtBuildDetail.processBuildResult(data, buildStartTime, eta, buildFinished);
            rtBuildDetail.processSteps(data);

            privFunc.updateArtifacts(data);

            //If build is running
            if (buildEndTime === null) {
                //Elapsed Time & Progress Bar
                timeElements.addElapsedElem($('#elapsedTimeJs'), buildStartTime);
            }

            timeElements.updateTimeObjects();
        },
        processBuildResult: function (data, startTime, eta, buildFinished) {
            var $buildResult = $('#buildResult');
            timeElements.clearTimeObjects($buildResult);
            var progressBar = "";
            if (eta !== 0) {
                progressBar = mustache.render(builders,
                    {progressBar: true, etaStart: startTime, etaCurrent: eta});
            }

            var props = {
                buildResults: true,
                b: data,
                buildIsFinished: buildFinished,
                progressBar: progressBar
            };

            var html = buildHandle(props);
            $buildResult.html(html);

            var $progressBar = $buildResult.find(".percent-outer-js");
            $progressBar.addClass("build-detail-progress");
            helpers.delegateToProgressBar($progressBar);
        },
        processSteps: function (data) {
            var html = "";
            var $stepList = $('#stepList');
            var count = 1;
            /*jslint unparam: true*/
            $.each(data.steps, function (i, stepData) {
                if (stepData.hidden) {
                    return true;
                }

                var started = stepData.isStarted;
                var finished = stepData.isFinished;

                var status = stepData.results[0];
                if (!started) {
                    status = helpers.cssClassesEnum.NOT_STARTED;
                } else if (started && !finished) {
                    status = helpers.cssClassesEnum.RUNNING;
                }

                stepData.hasURLs = Object.keys(stepData.urls).length > 0;
                $.each(stepData.urls, function (i, url) {
                    if (url.url !== undefined) {
                        stepData.hasDependency = true;
                        return false;
                    }
                    return true;
                });

                var cssClass = helpers.getCssClassFromStatus(status);
                var startTime = stepData.times[0];
                var endTime = stepData.times[1];
                var runTime = helpers.getTime(startTime, endTime);
                var props = {
                    step: true,
                    index: count,
                    stepStarted: stepData.isStarted,
                    run_time: runTime,
                    css_class: cssClass,
                    s: stepData,
                    url: stepData.url
                };
                html += buildHandle(props);
                count += 1;

                return true;
            });
            /*jslint unparam: false*/

            $stepList.html(html);
        },
        refreshIfRequired: function (buildFinished) {
            //Deal with page reload
            if (!noMoreReloads && isLoaded && buildFinished) {
                window.location = window.location + '#finished';
                window.location.reload();
            }
            if (noMoreReloads === false) {
                noMoreReloads = buildFinished;
            }

            isLoaded = true;
        }
    };

    return rtBuildDetail;
});