# Guanlecoja-ui

Note: This package is not maintained for uses outside Buildbot.

Implements generic application base for angular.js, ui.router and bootstrap3, with less.

To use:

* `bower install guanlecoja-ui`
* Include `scripts.js` and `styles.css` to your page.
* Include boostrap3, and font-awesome css.
* Make your app depend on `guanlecoja.ui` angular module.

Directives and services are prefixed with `gl`

## Directives

### glPageWithSidebar

Implements styles and behaviour for a menu with following features:

* Menu appears from left side, when mouse over
* Supports 1 level of sub-menus
* Menus icon from Font-Awesome
* Programmatic declaration, integrated with ui-router. Extracts menu from $state
* Supports pin for always expanded menu


The directive takes no argument and is configured via `glMenuServiceProvider` and `$stateProvider`

### glNotification

Implements styles and behaviour for widget centralizing your app's notifications:

* Listens for $http errors, and automatically shows them as notification
* associated service for other components to broadcast notification

The directive takes no argument and is configured via `glNotificationService`

### glTopbar

Implements a topbar holding the page's title and breadcrumb as well as optional contextual widgets.
It automatically calculate the breadcrumb from $state, with menu group information.

The directive takes no argument and is configured via `glBreadcrumbService`, `$stateProvider` and `glMenuServiceProvider`

The directive is transcluded. The childrens are included inside bootstrap3's ul.nav.navbar-nav.pull-right. It is made for contextual widgets like glNotification, or an authentication menu (not included).

### glTopbarContextualActions

Implements buttons on the topbar for implementing contextual actions.
It automatically generate buttons given the configuration. The configuration is reset at each $state change.

The directive takes no argument and is configured via `glTopbarContextualActionsService`

## Services
### glMenuServiceProvider

Configuration entrypoint for the sidebar menu

#### `glMenuServiceProvider.addGroup(group)`

Declare a group in the menu. takes on object with the following attributes:

* `name`: Name of the menu, identifier for reference in menu items
* `caption`: Text of the menu, as shown in the UI
* `icon`: Icon name from font-awesome. E.g `bug` will use the `fa-bug` class for the icon
* `order`: The menu is reordered according to this key. This allows to declare menus in different modules, without caring about the module load order.

#### `glMenuServiceProvider.setDefaultGroup(group)`

Declare a group to be the default group. Can be used directly after the `addGroup(group)` call.

#### `glMenuServiceProvider.setFooter(footer_items)`

Declare the menu footer links. The menu contains up to three footer button, that can be used for arbitrary external links. `footer_items` is a list of objects with following attributes:

* `caption`: text of the button
* `href`: link of the button

#### `glMenuServiceProvider.setAppTitle(title)`

Specify the application title. The text is shown in either the side menu, and in the topBar

#### `$stateProvider.state(state)`

Menu items are defined in `$stateProvider.state`'s data. glMenuService scans the list of states to find the menu items. You can use `state.data` for the usage you want, but glMenuService will look at the following attributes:

* `group`: name of the group to which append this menu-item
* `caption`: text of the menu-item

### glBreadcrumbService

Set the breadcrumbs of glTopMenu. In some cases, the automated breadcrumb from glTopMenu is unsuitable. In this case, you can use glBreadcrumbService to override it.

#### `glBreadcrumbService.setBreadcrumb(breadcrumb_list)`

breadcrumb_list is a list of objects containing following attributes:

* `caption`: text of the breadcrumb item
* `href`: optional href for the breadcrumb
* `sref`: optional sref for the breadcrumb. see ui.router's doc for more information about sref format.

Dont put both `sref` and `href` argument, this does not make sense and is not supported.

### glTopbarContextualActionsService

Set the contextual actions of glTopMenuContextualActions. You must instantiate the gl-topbar-contextual-actions directive inside a gl-topbar

#### `glTopbarContextualActionsService.setContextualActions(action_list)`

action_list is a list of objects containing following attributes:

* `caption`: text of the button item
* `help`: text for the help tooltip
* `icon`: optional icon for the button
* `action`: function called when the button is clicked

### glNotificationService

API for storing notifications. glNotification directive uses this service to display the notifications.

#### `glNotificationService.notify(notification)`

adds a notification to the notification system. notification is an object with following attributes:

* `title`: Title of the notification
* `msg`: Longer message for the notification
* `group`: glNotificationService supports grouping several notification of the same group together.

Messages of the same group will be concatenated with carriage return, and share the same title (only first title is kept, other titles are ignored)

#### `glNotificationService.error(notification)`

shortcut for `notify` with title to be `Error`.

#### `glNotificationService.network(notification)`

Shortcut for `notify` with title to be `Network Error`, and group to be `Network`

#### `glNotificationService.dismiss(id)`

Remove a notification from the list.

#### `glNotificationService.notifications`

The stored list of notifications.

## ChangeLog

* 2.0.0: This package is not maintained for use outside Buildbot.
         Rewrite the package from CoffeeScript to plain JavaScript.
* 1.8.0: body is no more height:100%, in order to make full height page, user need to use height: 100vh.
         left-bar pinned preference is now stored in the browser.
* 1.7.0: topbar is now responsive. It will collapse on mobile.
* 1.6.3: Adds setDefaultGroup(group) to glMenuServiceProvider. This option allows to expand a menu by default
* 1.6.2: Fix width issues of content which push some content off-screen for certain monitor size
* 1.6.1: rebuilt with guanlecoja 1.7.2, which populates the BOWERDEPS metadata
* 1.6.0: Massive upgrade of dependencies:
    - jquery 2.1 -> 2.2.
    - Angular 1.4 -> 1.5.
    - Lodash -> 4.11.
    - Drop underscore.string as lodash got most important string utils.
    - angular-ui-bootstrap 0.11 -> 1.3.2:
        Most important change is that ui-bootstrap directives are now prefixed with "uib-" e.g: in jade: ".dropdown-toggle" -> ".dropdown-toggle(uib-dropdown-toggle)"
        This makes the markup more complicated, but the old 0.11 documentation is not even available anymore, so its best to upgrade.
* 1.5.0: Switch to angularJS 1.4.3
* 1.4.2: fix the sidebar when screen is > 800px
* 1.4.1: bump ui-router version to 0.2.13
* 1.4.0: add topbar-contextual-actions directive and associated service
* 1.3.1: Fix auto scrollbar on sidebar menu
* 1.3.0: Switch to angularJS 1.3.1
* 1.2.3: Initial Release

## Credits


Original Design by Elliot Hesp:
https://github.com/Ehesp/Responsive-Dashboard
