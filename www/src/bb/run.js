require(["bb/router", "moment/moment"], function(router, moment) {
    console.log(moment.unix(329384734).format('LLLL'));
    bb_router = router( {
        // TODO: router should get these values from dojo.config
        ws_url: "%(ws_url)s",
        static_url:"%(static_url)s",
        base_url:"%(base_url)s",
        extra_routes:"%(extra_routes)s"}
    );
});
