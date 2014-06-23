angular.module('buildbot.console_view').directive 'sticky',
  ['$document', '$window', ($document, $window) ->
      replace: false
      restrict: 'A'
      link: (scope, element, attrs) ->

          prefixes = ['-webkit-', '-moz-', '-ms-', '-o-', '']
          elementOffsetTop = element.offset().top
          attrOffset = Math.min(attrs.offset ?= 0, elementOffsetTop)

          $document.bind 'scroll', ->
              offset = elementOffsetTop - attrOffset
              scrollY = document.documentElement.scrollTop or $window.scrollY
              if scrollY - offset > 0
                  for prefix in prefixes
                      element.css "#{prefix}transform",
                        "translate3d(0,#{scrollY - offset}px,0)"
              else
                  for prefix in prefixes
                      element.css "#{prefix}transform", "translate3d(0,0,0)"
  ]