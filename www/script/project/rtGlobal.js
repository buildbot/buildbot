/*global define, requirejs*/
define(function (require) {
    "use strict";

    var $ = require('jquery'),
        helpers = require('helpers'),
        dt = require('project/datatables-extend'),
        popup = require('ui.popup'),
        extendMoment = require('project/moment-extend'),
        buildQueueTotal = $('#buildQueueTotal'),
        buildSlavesTotal = $('#buildSlavesTotal'),
        outerBar = $('#verticalProgressBar'),
        imageTotalBuildsBox = $('#buildsTotal'),
        $buildLoadBox = $('#buildLoad'),
        infoSpan = $buildLoadBox.find('span'),
        minBuildsPerSlave = 3, // The amount of builds each agent is allowed to have before we get yellow build load
        maxBuildsPerSlave = 5, // The amount of builds each agent is allowed to have before we get red build load
        buildLoad = 0,
        bKatanaLoaded = false;

    var rtGlobal = {
        init: function () {
            requirejs(['realtimePages'], function (realtimePages) {
                rtGlobal.initDataTable();
                var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
                realtimePages.initRealtime(realtimeFunctions);
            });
        },
        processGlobalInfo: function (data) {
            extendMoment.setServerTime(data.utc);
            buildLoad = data.build_load;

            var buildLoadPerSlave = buildLoad / data.slaves_count,
                statusColorClass = buildLoadPerSlave <= minBuildsPerSlave ? 'green' : buildLoadPerSlave <= maxBuildsPerSlave ? 'yellow' : 'red';
            var buildsCountYesterday = data.total_builds_lastday;
            
            bKatanaLoaded = buildLoadPerSlave > maxBuildsPerSlave;

            buildQueueTotal.show();
            buildSlavesTotal.show();
            outerBar.show();

            $buildLoadBox.attr({'class': 'info-box ' + statusColorClass}).show();

            var slaveCount = data.slaves_count;
            var slavesInUsePer = (data.slaves_busy / slaveCount) * 100.0;
            var slavesFree = slaveCount - data.slaves_busy;
            var runningBuilds = data.running_builds;


            helpers.verticalProgressBar(outerBar.children(), slavesInUsePer);
            outerBar.attr("title", "{0} builds are running, {1}, agents are idle".format(runningBuilds, slavesFree));

            buildSlavesTotal.text(slaveCount);
            infoSpan.text(buildLoad);
            imageTotalBuildsBox.text(buildsCountYesterday);
        },
        initDataTable: function () {
            var $table = $('.tablesorter-js');
            if ($table.length === 0) {
                $table = $('#tablesorterRt');
            }

            $.each($table, function (i, elem) {
                dt.initTable($(elem), {});
            });
        },
        getBuildLoad: function getBuildLoad() {
            return buildLoad;
        },
        isKatanaLoaded: function isKatanaLoaded() {
            return bKatanaLoaded;
        }
    };

    return rtGlobal;
});