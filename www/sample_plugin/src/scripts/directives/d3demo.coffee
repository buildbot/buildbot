angular.module("app").directive "d3demo", ["sample_plugin_config", (config) ->
  restrict: "E"
  scope:
    val: "="
    grouped: "="

  # d3 example coming from: http://bl.ocks.org/mbostock/1353700
  link: (scope, element, attrs) ->
    gear = (d) ->
      n = d.teeth
      r2 = Math.abs(d.radius)
      r0 = r2 - 8
      r1 = r2 + 8
      if d.annulus
        r3 = r0
        r0 = r1
        r1 = r3
        r3 = r2 + 20
      else
        r3 = 20
      da = Math.PI / n
      a0 = -Math.PI / 2 + ((if d.annulus then Math.PI / n else 0))
      i = -1
      path = ["M", r0 * Math.cos(a0), ",", r0 * Math.sin(a0)]
      while ++i < n
        path.push( "A", r0, ",", r0, " 0 0,1 ", r0 * Math.cos(a0 += da), ",", r0 * Math.sin(a0),
                   "L", r2 * Math.cos(a0), ",", r2 * Math.sin(a0),
                   "L", r1 * Math.cos(a0 += da / 3), ",", r1 * Math.sin(a0),
                   "A", r1, ",", r1, " 0 0,1 ", r1 * Math.cos(a0 += da / 3), ",", r1 * Math.sin(a0),
                   "L", r2 * Math.cos(a0 += da / 3), ",", r2 * Math.sin(a0),
                   "L", r0 * Math.cos(a0), ",", r0 * Math.sin(a0)
          )
      path.push "M0,", -r3, "A", r3, ",", r3, " 0 0,0 0,", r3, "A", r3, ",", r3, " 0 0,0 0,", -r3, "Z"
      path.join ""
    width = 960
    height = 500
    radius = 80
    x = Math.sin(2 * Math.PI / 3)
    y = Math.cos(2 * Math.PI / 3)
    offset = 0
    speed = 4
    if config.rotate_speed?
      speed = config.rotate_speed
    start = Date.now()
    console.log element
    svg = d3.select(element[0]).append("svg")
            .attr("width", width)
            .attr("height", height)
            .append("g")
            .attr("transform", "translate(" + width / 2 + "," + height / 2 + ")scale(.55)").append("g")

    frame = svg.append("g").datum(radius: Infinity)
    frame.append("g").attr("class", "annulus").datum(
      teeth: 80
      radius: -radius * 5
      annulus: true
    ).append("path").attr "d", gear
    frame.append("g").attr("class", "sun").datum(
      teeth: 16
      radius: radius
    ).append("path").attr "d", gear
    frame.append("g").attr("class", "planet").attr("transform", "translate(0,-" + radius * 3 + ")").datum(
      teeth: 32
      radius: -radius * 2
    ).append("path").attr "d", gear
    frame.append("g").attr("class", "planet").attr("transform", "translate(" + -radius * 3 * x + "," + -radius * 3 * y + ")").datum(
      teeth: 32
      radius: -radius * 2
    ).append("path").attr "d", gear
    frame.append("g").attr("class", "planet").attr("transform", "translate(" + radius * 3 * x + "," + -radius * 3 * y + ")").datum(
      teeth: 32
      radius: -radius * 2
    ).append("path").attr "d", gear

    d3.timer ->
      angle = (Date.now() - start) * speed
      console.log speed
      transform = (d) ->
        "rotate(" + angle / d.radius + ")"

      frame.selectAll("path").attr "transform", transform
      frame.attr "transform", transform # frame of reference
      return false
]
