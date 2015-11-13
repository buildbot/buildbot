This directory contains SVG templates to produce the Buildbot PngStatusResource
files that tell us the build status for a given build of a given builder.

The SVG files has been created with Inkscape-0.48.4 under Gentoo GNU/Linux for
x86_64 architecture.


Howto generate the PNG files?
=============================
There are two different ways for generate the PNG files using inkscape.

    1) For non GUI users
        Just edit the SVG files (as those are just XML files) with your
        favourite text editor (vi, emacs, nano, joe...). The SVG image is
        composed by layers so for any buildbot status we have a layer with
        two components, the status text and the background color, there are
        some other layers containing glows and static text that never changes
        (like thw "build" word) so you dont have to care about.

        Each layer has a descriptive name, for exmaple, the layer for failed
        builds is called "rectFailed", "rectSuccess" for success, "rectExcept"
        for exceptions and so on.

        Each status layer has two components, the statsu text and the status
        background, text is just a "tspan" markup and looks like this:

            <tspan y="15" x= "2" id="tspan367" sodipodi:role="line">
                success
            </tspan>

        The entire <tspan> should be inside a <text> markup that we don't care
        about if we are not going to increade the size or the family of the
        used font.

        The background component is not more complex that the previous one, it
        is built using a <rect> markup that looks like:

            <rect
                style="fill:#cc66cc;fill-opacity:1;stroke:none;display:inline"
                id="rect3675"
                with="32"
                height="14"
                x="0"
                y="4"
                rx="4.2"
                ry="4.01"
            />

        The properties are pretty self descriptives, with the "style" property
        we control the look of the rect, in the previous example we are
        generating a rect with filled purple color without opacity no stroke
        and displayed inline, the rest of properties are just size and position
        in the canvas.

        To change teh color we just need to modify the #hexcolor in the style
        property.

        As we said before, some layers are just hidden while other are visible,
        to export one build status we need to make visible the related layers
        to the status we want to generate.

        The layers have also a "style" property in their definitions, the
        hidden layers have it setted as "display:none" while the visible ones
        have it as "display:inline" show or hidden layers is as easy as change
        the values for layers that we want to hide or show.

        To create a new group we only have to copy a full layer block and paste
        it modifying the layer name and the new property values we require
        (that usually are just the backgound color and the text of tspan).

        When we are ok with our changes to the SVG file we can just execute
        inkscape in the command line to export it to PNG format:

             inkscape -z -e status_size.png status_size.svg

        The -z option tells inkscape to don't use a graphical user interface,
        the -e is just "export command" followed by the name of the new
        exported file (status_size.png in our example) and the last argument
        is just the name of the SVG file that we modified previously.

    2) For GUI users
        Well, if you never used Inkscape before, I suggest to check the basic
        tutorial in their website, and then come back here:

            http://inkscape.org/doc/basic/tutorial-basic.html

        Our SVG files are compound by layers, some layers are pretty static and
        them are "locked", that means that you can't click on the components
        inside the layers so you can't select them to modify it.

        The first thing you have to do is show the layers window using the
        shortcut Ctrl+Shift+L

        In this window you can see all the layers thart build the SVG file, you
        can hide or make them visible clicking in the eye at the most left side
        of the layer name. Next to this eye button is a "chain" button that is
        used to lock or unlock any layer.

        Each status layer has a descriptive name like "rectSuccess" for the
        success buildbot status (rectFailed for failed etc). Them are compound
        of two shapes:

            The status text
            The status background

        To change the text we have to select it and then click on the Text
        tool in the left side of the main window, then the cursor over the
        text shape in the draw should change and we can just write on it. On
        the top of the main window we can see a toolset for adjust properties
        of the text (I recommend the reading of Inkscape tutorials to really
        understand how all this works).

        To change the background color for the status we need to show the
        "Fill and Stroke" menu using the shortcut "Ctrl+Shift+F"

        Then if we click on the rect shape we can check and modify all the
        related properties and values about the object look.

        To change the color we should modify the RGBA (in hex format) value
        in the color form. Note that the last two characters of the hex format
        controls the object alpha layer so FF is no opacity at all while 00
        is total opacity, be careful and rememeber that when you modify the
        color by hand.

        To create a new layer you can just do right click on any of the already
        existing status layers and select "Duplicate layer" in the context menu
        that should be shown. Then you can modify the layer as your needs and
        save it

        To understand how to export from the SVG file to PNG format I reommend
        to read this article about Inkscape export system:

            http://inkscape.org/doc/basic/tutorial-basic.html

        Anyway my preffer method is the one described in "Non GUI Users" just
        using the command line.
