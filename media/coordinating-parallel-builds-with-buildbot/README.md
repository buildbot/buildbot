# Mozilla Evangelism Reps shower

This is the HTML5 slide deck system created to make it easier for Mozilla evangelism reps to get started with their presentations.

* Based on [@pepelsbey](http://twitter.com/pepelsbey)'s original shower system available on [https://github.com/pepelsbey/shower](https://github.com/pepelsbey/shower)
* Licensed under [MIT License](http://en.wikipedia.org/wiki/MIT_License), see [license page](https://github.com/pepelsbey/shower/wiki/License-En) for details.

## Enhancements

* Speaker notes using console.log()
* Smooth transitions between slides
* Option to turn off slide numbers
* left/right placement of images
* Image frames / swinging animation

## How to use

The way to present these slides is explained in detail [in this screencast](http://www.youtube.com/watch?v=5xBfy8mN1iQ)

## Editing slides

The mozilla-example.html file contains all the possible slides the system supports. Simply copy the ones you need and delete the others. There are also comments to explain the global switches for the system.

### General edits to the slide system

There are a few things you can change in the overall document:

* Smooth transitions - by default there is a one second transition using opacity for fading in between slides. This is triggered by the class "fade" on the HTML elements. If you remove it, slides just pop from one to another.
* Progress bar - the progress bar can be removed by deleting the DIV with the class "progress" at the bottom of the document
* Slide numbers - if you want to remove the slide numbers, add a class of "nonumbers" to the HTML element

### Slides

* Each slide needs a unique ID and the class of slide to be recognised by the system and to be navigated to.
* Each slide has a header and a footer - the presenter notes go into the footer of the slide. They are not shown by default. You can roll over the slides in list view to see them and during presenting they'll be shown in the debugging console of the browser.
* Each slide needs a H2 header to show as the "NEXT" information in the speaker note display.

### Lists

You can control the display of lists by adding various classes to the UL element:

* "longlist" applies a smaller font so that you can add more items
* "inline" turns the list into comma separated words followed by a full stop.
* "oneline" puts all list items on one line
* "inner" adds in-slide navigation to the list. You need to set a class of "active" to the first LI to show the items one by one rather than all at the same time

### Images

* Adding a class of "middle", "left" or "right" to any IMG element positions it on the screen.
* Slides with a class of "cower" will show the image as a background with the headings becoming white with a half-opaque black background. You can add a "w" or "h" class to the slide to fit the background image to the width or the height respectively.
* Adding a FIGURE element around the image allows you to add extra features by adding one or more of the following classes to the FIGURE:
- Adding a "shadow" class gives it a drop shadow
- Adding a "frame" class makes the image look like it is hanging from a nail
- Adding a "swing" class adds an animation to dangle it from the nail.
