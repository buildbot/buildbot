# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members
#
# Original Version by jean-philippe Serafin
# https://github.com/jeanphix/Ghost.py
# Original License: MIT
#
# buildbot version adapted to run inside twisted/trial

import sys
import os
import time
import codecs
import json
import subprocess
from functools import wraps
from twisted.internet import defer, reactor
from twisted.python import log

try:
    import sip
    sip.setapi('QVariant', 2)
    from PyQt4 import QtWebKit
    from PyQt4.QtNetwork import QNetworkRequest, QNetworkAccessManager,\
                                QNetworkCookieJar, QNetworkDiskCache
    from PyQt4.QtCore import QSize, QByteArray, QUrl
    from PyQt4.QtGui import QApplication, QImage, QPainter

    # pyflakes does not like redefinition of unused symbols implemented in case of import error
    (QtWebKit , QNetworkRequest , QNetworkAccessManager , QNetworkCookieJar , QNetworkDiskCache,
     QSize, QByteArray, QUrl, QApplication, QImage, QPainter)
except ImportError:
    try:
        from PySide import QtWebKit
        from PySide.QtNetwork import QNetworkRequest, QNetworkAccessManager,\
                                    QNetworkCookieJar, QNetworkDiskCache
        from PySide.QtCore import QSize, QByteArray, QUrl
        from PySide.QtGui import QApplication, QImage, QPainter
    except ImportError:
        raise ImportError("Ghost.py requires PySide or PyQt")


default_user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.2 " +\
    "(KHTML, like Gecko) Chrome/15.0.874.121 Safari/535.2"




class GhostWebPage(QtWebKit.QWebPage):
    """Overrides QtWebKit.QWebPage in order to intercept some graphical
    behaviours like alert(), confirm().
    Also intercepts client side console.log().
    """
    def chooseFile(self, frame, suggested_file=None):
        return Ghost._upload_file

    def javaScriptConsoleMessage(self, message, line, source):
        """Prints client console message in current output stream."""
        super(GhostWebPage, self).javaScriptConsoleMessage(message, line,
            source)
        log.msg("%s(%d): %s" % (source or '<unknown>', line, message),system="Ghost:console")

    def javaScriptAlert(self, frame, message):
        """Notifies ghost for alert, then pass."""
        Ghost._alert = message
        log.msg("alert('%s')" % message,system="Ghost:Alert")

    def javaScriptConfirm(self, frame, message):
        """Checks if ghost is waiting for confirm, then returns the right
        value.
        """
        if Ghost._confirm_expected is None:
            raise Exception('You must specified a value to confirm "%s"' %
                message)
        confirmation, callback = Ghost._confirm_expected
        Ghost._confirm_expected = None
        log.msg("confirm('%s')" % message,system="Ghost:Confirm")
        if callback is not None:
            return callback()
        return confirmation

    def javaScriptPrompt(self, frame, message, defaultValue, result=None):
        """Checks if ghost is waiting for prompt, then enters the right
        value.
        """
        if Ghost._prompt_expected is None:
            raise Exception('You must specified a value for prompt "%s"' %
                message)
        result_value, callback = Ghost._prompt_expected
        log.msg("prompt('%s')" % message,system="Ghost:Prompt")
        if callback is not None:
            result_value = callback()
        if result_value == '':
            log.msg("'%s' prompt filled with empty string" % message,system="Ghost:Prompt")
        Ghost._prompt_expected = None
        if result is None:
            # PySide
            return True, result_value
        result.append(result_value)
        return True


def can_load_page(func):
    """Decorator that specifies if user can expect page loading from
    this action. If expect_loading is set to True, ghost will wait
    for page_loaded event.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        expect_loading = False
        if 'expect_loading' in kwargs:
            expect_loading = kwargs['expect_loading']
            del kwargs['expect_loading']
        if expect_loading:
            self.loaded = False
            func(self, *args, **kwargs)
            return self.wait_for_page_loaded()
        return func(self, *args, **kwargs)
    return wrapper


def client_utils_required(func):
    """Decorator that checks avabality of Ghost client side utils,
    injects require javascript file instead.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.global_exists('GhostUtils'):
            self.evaluate_js_file(
                os.path.join(os.path.dirname(__file__), 'utils.js'))
        return func(self, *args, **kwargs)
    return wrapper


class HttpResource(object):
    """Represents an HTTP resource.
    """
    def __init__(self, reply, cache):
        self.url = reply.url().toString()
        try:
            buffer = cache.data(self.url)
        except TypeError:
            buffer = cache.data(reply.url())
        self.content = None
        if buffer is not None:
            self.content = unicode(buffer.readAll(),"ascii","ignore")
        self.http_status = reply.attribute(
            QNetworkRequest.HttpStatusCodeAttribute)
        log.msg("Resource loaded: %s %s" % (self.url, self.http_status),system="Ghost:Http")
        self.headers = {}
        for header in reply.rawHeaderList():
            self.headers[unicode(header)] = unicode(reply.rawHeader(header))
        self._reply = reply


class Ghost(object):
    """Ghost manages a QWebPage.

    :param user_agent: The default User-Agent header.
    :param wait_timeout: Maximum step duration in second.
    :param wait_callback: An optional callable that is periodically
        executed until Ghost stops waiting.
    :param log_level: The optional logging level.
    :param display: A boolean that tells ghost to displays UI.
    :param viewport_size: A tupple that sets initial viewport size.
    """
    _alert = None
    _confirm_expected = None
    _prompt_expected = None
    _upload_file = None
    _app = None

    def __init__(self, user_agent=default_user_agent, wait_timeout=8,
            wait_callback=None, display=False,
            viewport_size=(800, 600), cache_dir='/tmp/ghost.py'):
        self.http_resources = []

        self.user_agent = user_agent
        self.wait_timeout = wait_timeout
        self.wait_callback = wait_callback

        self.loaded = True

        if not sys.platform.startswith('win') and not 'DISPLAY' in os.environ\
                and not hasattr(Ghost, 'xvfb'):
            try:
                os.environ['DISPLAY'] = ':99'
                Ghost.xvfb = subprocess.Popen(['Xvfb', ':99'])
            except OSError:
                raise Exception('Xvfb is required to a ghost run oustside ' +\
                    'an X instance')

        self.display = display

        if not Ghost._app:
            Ghost._app = QApplication.instance() or QApplication(['ghost'])

        self.page = GhostWebPage(Ghost._app)
        QtWebKit.QWebSettings.setMaximumPagesInCache(0)
        QtWebKit.QWebSettings.setObjectCacheCapacities(0, 0, 0)

        self.set_viewport_size(*viewport_size)

        self.page.loadFinished.connect(self._page_loaded)
        self.page.loadStarted.connect(self._page_load_started)

        self.manager = self.page.networkAccessManager()
        self.manager.finished.connect(self._request_ended)
        # Cache
        self.cache = QNetworkDiskCache()
        self.cache.setCacheDirectory(cache_dir)
        self.manager.setCache(self.cache)
        # Cookie jar
        self.cookie_jar = QNetworkCookieJar()
        self.manager.setCookieJar(self.cookie_jar)

        self.page.networkAccessManager().authenticationRequired\
            .connect(self._authenticate)
        self.page.networkAccessManager().proxyAuthenticationRequired\
            .connect(self._authenticate)

        self.main_frame = self.page.mainFrame()


        if self.display:
            self.webview = QtWebKit.QWebView()
            self.webview.setPage(self.page)
            self.webview.show()

    def __del__(self):
        self.exit()

    def capture(self, region=None, selector=None, format=QImage.Format_ARGB32):
        """Returns snapshot as QImage.

        :param region: An optional tupple containing region as pixel
            coodinates.
        :param selector: A selector targeted the element to crop on.
        :param format: The output image format.
        """
        if region is None and selector is not None:
            region = self.region_for_selector(selector)
        if region:
            x1, y1, x2, y2 = region
            w, h = (x2 - x1), (y2 - y1)
            image = QImage(QSize(x2, y2), format)
            painter = QPainter(image)
            self.main_frame.render(painter)
            painter.end()
            image = image.copy(x1, y1, w, h)
        else:
            image = QImage(self.page.viewportSize(), format)
            painter = QPainter(image)
            self.main_frame.render(painter)
            painter.end()
        return image

    def capture_to(self, path, region=None, selector=None,
        format=QImage.Format_ARGB32):
        """Saves snapshot as image.

        :param path: The destination path.
        :param region: An optional tupple containing region as pixel
            coodinates.
        :param selector: A selector targeted the element to crop on.
        :param format: The output image format.
        """
        self.capture(region=region, format=format,
            selector=selector).save(path)

    @client_utils_required
    @can_load_page
    def click(self, selector):
        """Click the targeted element.

        :param selector: A CSS3 selector to targeted element.
        """
        if not self.exists(selector):
            raise Exception("Can't find element to click")
        return self.evaluate('GhostUtils.click("%s");' % selector)

    class confirm:
        """Statement that tells Ghost how to deal with javascript confirm().

        :param confirm: A bollean that confirm.
        :param callable: A callable that returns a boolean for confirmation.
        """
        def __init__(self, confirm=True, callback=None):
            self.confirm = confirm
            self.callback = callback

        def __enter__(self):
            Ghost._confirm_expected = (self.confirm, self.callback)

        def __exit__(self, type, value, traceback):
            Ghost._confirm_expected = None

    @property
    def content(self):
        """Returns current frame HTML as a string."""
        return unicode(self.main_frame.toHtml())

    @property
    def cookies(self):
        """Returns all cookies."""
        return self.cookie_jar.allCookies()

    def delete_cookies(self):
        """Deletes all cookies."""
        self.cookie_jar.setAllCookies([])

    @can_load_page
    def evaluate(self, script):
        """Evaluates script in page frame.

        :param script: The script to evaluate.
        """
        return (self.main_frame.evaluateJavaScript("%s" % script),
            self._release_last_resources())
    def inject_script(self, script):
        self.evaluate(
        """(function(){e = document.createElement("script");
        e.type = "text/javascript";
        e.textContent = JSON.parse("%s")
        e.charset = "utf-8";
        document.getElementsByTagName("head")[0].appendChild(e);
        })()
        """%(json.dumps(script).replace('"','\\"'))
        )
    def evaluate_js_file(self, path, encoding='utf-8'):
        """Evaluates javascript file at given path in current frame.
        Raises native IOException in case of invalid file.

        :param path: The path of the file.
        :param encoding: The file's encoding.
        """
        self.evaluate(codecs.open(path, encoding=encoding).read())

    def exists(self, selector):
        """Checks if element exists for given selector.

        :param string: The element selector.
        """
        return not self.main_frame.findFirstElement(selector).isNull()

    def exit(self):
        """Exits application and relateds."""
        if self.display:
            self.webview.close()
        Ghost._app.exit()
        del self.manager
        del self.page
        del self.main_frame
        if hasattr(self, 'xvfb'):
            self.xvfb.terminate()

    @can_load_page
    def fill(self, selector, values):
        """Fills a form with provided values.

        :param selector: A CSS selector to the target form to fill.
        :param values: A dict containing the values.
        """
        if not self.exists(selector):
            raise Exception("Can't find form")
        resources = []
        for field in values:
            r, res = self.set_field_value("%s [name=%s]" % (selector, field),
                values[field])
            resources.extend(res)
        return True, resources

    @client_utils_required
    @can_load_page
    def fire_on(self, selector, method):
        """Call method on element matching given selector.

        :param selector: A CSS selector to the target element.
        :param method: The name of the method to fire.
        :param expect_loading: Specifies if a page loading is expected.
        """
        return self.evaluate('GhostUtils.fireOn("%s", "%s");' % (
            selector, method))

    def global_exists(self, global_name):
        """Checks if javascript global exists.

        :param global_name: The name of the global.
        """
        return self.evaluate('!(typeof %s === "undefined");' %
            global_name)[0]

    def hide(self):
        """Close the webview."""
        try:
            self.webview.close()
        except:
            raise Exception("no webview to close")

    def open(self, address, method='get', headers={}, auth=None):
        """Opens a web page.

        :param address: The resource URL.
        :param method: The Http method.
        :param headers: An optional dict of extra request hearders.
        :param auth: An optional tupple of HTTP auth (username, password).
        :return: Page resource, All loaded resources.
        """
        body = QByteArray()
        try:
            method = getattr(QNetworkAccessManager,
                "%sOperation" % method.capitalize())
        except AttributeError:
            raise Exception("Invalid http method %s" % method)
        request = QNetworkRequest(QUrl(address))
        request.CacheLoadControl(0)
        if not "User-Agent" in headers:
            headers["User-Agent"] = self.user_agent
        for header in headers:
            request.setRawHeader(header, headers[header])
        self._auth = auth
        self._auth_attempt = 0  # Avoids reccursion
        self.main_frame.load(request, method, body)
        self.loaded = False
        return self.wait_for_page_loaded()

    class prompt:
        """Statement that tells Ghost how to deal with javascript prompt().

        :param value: A string value to fill in prompt.
        :param callback: A callable that returns the value to fill in.
        """
        def __init__(self, value='', callback=None):
            self.value = value
            self.callback = callback

        def __enter__(self):
            Ghost._prompt_expected = (self.value, self.callback)

        def __exit__(self, type, value, traceback):
            Ghost._prompt_expected = None

    @client_utils_required
    def region_for_selector(self, selector):
        """Returns frame region for given selector as tupple.

        :param selector: The targeted element.
        """
        geo = self.main_frame.findFirstElement(selector).geometry()
        try:
            region = (geo.left(), geo.top(), geo.right(), geo.bottom())
        except:
            raise Exception("can't get region for selector '%s'" % selector)
        return region

    @can_load_page
    @client_utils_required
    def set_field_value(self, selector, value, blur=True):
        """Sets the value of the field matched by given selector.

        :param selector: A CSS selector that target the field.
        :param value: The value to fill in.
        :param blur: An optional boolean that force blur when filled in.
        """
        def _set_text_value(selector, value):
            return self.evaluate(
                'document.querySelector("%s").value=%s;' %
                    (selector, json.dumps(value)))

        res, resources = None, []

        element = self.main_frame.findFirstElement(selector)
        if element.isNull():
            raise Exception('can\'t find element for %s"' % selector)
        self.fire_on(selector, 'focus')
        if element.tagName() in ["TEXTAREA", "SELECT"]:
            res, resources = _set_text_value(selector, value)
        elif element.tagName() == "INPUT":
            if element.attribute('type') in ["color", "date", "datetime",
                "datetime-local", "email", "hidden", "month", "number",
                "password", "range", "search", "tel", "text", "time",
                "url", "week"]:
                res, resources = _set_text_value(selector, value)
            elif element.attribute('type') == "checkbox":
                res, resources = self.evaluate(
                    'GhostUtils.setCheckboxValue("%s", %s);' %
                        (selector, json.dumps(value)))
            elif element.attribute('type') == "radio":
                res, resources = self.evaluate(
                    'GhostUtils.setRadioValue("%s", %s);' %
                        (selector, json.dumps(value)))
            elif element.attribute('type') == "file":
                Ghost._upload_file = value
                res, resources = self.click(selector)
                Ghost._upload_file = None
        else:
            raise Exception('unsuported field tag')
        if blur:
            self.fire_on(selector, 'blur')
        return res, resources

    def set_viewport_size(self, width, height):
        """Sets the page viewport size.

        :param width: An integer that sets width pixel count.
        :param height: An integer that sets height pixel count.
        """
        self.page.setViewportSize(QSize(width, height))

    def show(self):
        """Show current page inside a QWebView.
        """
        self.webview = QtWebKit.QWebView()
        self.webview.setPage(self.page)
        self.webview.show()

    @defer.inlineCallbacks
    def wait_for_alert(self):
        """Waits for main frame alert().
        """
        yield self._wait_for(lambda: Ghost._alert is not None,
            'User has not been alerted.')
        msg = Ghost._alert
        Ghost._alert = None
        yield msg, self._release_last_resources()

    @defer.inlineCallbacks
    def wait_for_page_loaded(self):
        """Waits until page is loaded, assumed that a page as been requested.
        """
        yield self._wait_for(lambda: self.loaded,
            'Unable to load requested page')
        resources = self._release_last_resources()
        page = None
        for resource in resources:
            if self.main_frame.url().toString() == resource.url:
                page = resource
        yield page, resources

    @defer.inlineCallbacks
    def wait_for_selector(self, selector):
        """Waits until selector match an element on the frame.

        :param selector: The selector to wait for.
        """
        yield self._wait_for(lambda: self.exists(selector),
            'Can\'t find element matching "%s"' % selector)
        yield True, self._release_last_resources()

    @defer.inlineCallbacks
    def wait_for_text(self, text):
        """Waits until given text appear on main frame.

        :param text: The text to wait for.
        """
        yield self._wait_for(lambda: text in self.content,
            'Can\'t find "%s" in current frame' % text)
        yield True, self._release_last_resources()

    def _authenticate(self, mix, authenticator):
        """Called back on basic / proxy http auth.

        :param mix: The QNetworkReply or QNetworkProxy object.
        :param authenticator: The QAuthenticator object.
        """
        if self._auth_attempt == 0:
            username, password = self._auth
            authenticator.setUser(username)
            authenticator.setPassword(password)
            self._auth_attempt += 1

    def _page_loaded(self):
        """Called back when page is loaded.
        """
        self.loaded = True
        self.cache.clear()

    def _page_load_started(self):
        """Called back when page load started.
        """
        self.loaded = False

    def _release_last_resources(self):
        """Releases last loaded resources.

        :return: The released resources.
        """
        last_resources = self.http_resources
        self.http_resources = []
        return last_resources

    def _request_ended(self, reply):
        """Adds an HttpResource object to http_resources.

        :param reply: The QNetworkReply object.
        """
        if reply.attribute(QNetworkRequest.HttpStatusCodeAttribute):
            self.http_resources.append(HttpResource(reply, self.cache))

    def _wait_for(self, condition, timeout_message):
        """Waits until condition is True.

        :param condition: A callable that returns the condition.
        :param timeout_message: The exception message on timeout.
        """
        d = defer.Deferred()
        started_at = time.time()
        def poll():
            # This function is a bit hacky. We do that
            # in order to avoid the need to run the whole trial
            # inside a qtreactor. We just install a polling callback
            # that will periodically run the qt event loop.
            try:
                if condition():
                    d.callback(None)
                    return
                if time.time() > (started_at + self.wait_timeout):
                    d.errback(Exception(timeout_message))
                    return
                Ghost._app.processEvents()
                reactor.callLater(0.001, poll)
            except Exception, e:
                d.errback(e)
        poll()
        return d
