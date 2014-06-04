define(['jquery', 'helpers', 'dataTables', 'extend-moment'], function ($, helpers, dt, extendMoment) {
    
    var buildQueueTotal = $('#buildQueueTotal');
    var buildSlavesTotal = $('#buildSlavesTotal');
    var outerBar = $('#verticalProgressBar');
    var $buildLoadBox = $('#buildLoad');
    var infoSpan = $buildLoadBox.find('span');
    var $attentionBox = $('#attentionBox');

    var rtGlobal = {
        init: function () {
            requirejs(['realtimePages'], function (realtimePages) {
                rtGlobal.initDataTable();
                var realtimeFunctions = realtimePages.defaultRealtimeFunctions();
                realtimePages.initRealtime(realtimeFunctions);
            });
        },
        processGlobalInfo: function (data) {
            extendMoment.setServerTime(data['utc']);
            
            if (helpers.isRealTimePage() === false) {
                $attentionBox.addClass('show-desktop');
            }

            var buildLoad = data['build_load'];

            buildQueueTotal.show();
            buildSlavesTotal.show();
            outerBar.show();             
                
            var statusColorClass = buildLoad <= 100? 'green': buildLoad >= 101 && buildLoad <= 200? 'yellow' : 'red';
            
            $buildLoadBox.attr({'class':'info-box '+statusColorClass}).show();            

            var slaveCount = data['slaves_count'];
            var slavesInUsePer = (data['slaves_busy'] / slaveCount) * 100.0;
            var slavesFree = slaveCount - data['slaves_busy'];
            var runningBuilds = data['running_builds'];
            

            helpers.verticalProgressBar(outerBar.children(), slavesInUsePer);
            outerBar.attr("title", "{0} builds are running, {1}, agents are idle".format(runningBuilds, slavesFree));

            buildSlavesTotal.text(slaveCount);
            infoSpan.text(buildLoad);
        },
        initDataTable : function() {
            var table = undefined;
            if ($('.tablesorter-js').length) {
                table = $('.tablesorter-js');
            } else {
                table = $('#tablesorterRt');
            }

            $.each(table, function(i, elem) {
                dt.initTable($(elem), {});
            });
        }
    };

    return rtGlobal;
});