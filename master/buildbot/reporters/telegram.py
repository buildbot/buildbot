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

import io
import json
import random

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.web import resource
from twisted.web import server

from buildbot import config
from buildbot import util
from buildbot.plugins.db import get_plugins
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters.words import Contact
from buildbot.reporters.words import StatusBot
from buildbot.util import bytes2unicode
from buildbot.util import httpclientservice
from buildbot.util import service
from buildbot.util import unicode2bytes


class TelegramContact(Contact):

    def __init__(self, bot, user=None, channel=None, _reactor=reactor):
        super().__init__(bot, user, channel, _reactor)
        self.partial = ''

    results_emoji = {
        SUCCESS: ' ✅',
        WARNINGS: ' ⚠️',
        FAILURE: '❗',
        EXCEPTION: ' ‼️',
        RETRY: ' 🔄',
        CANCELLED: ' 🚫',
    }

    def format_build_status(self, build, short=False):
        br = build['results']
        if short:
            return self.results_emoji[br]
        else:
            return self.results_descriptions[br] + \
                   self.results_emoji[br]

    @property
    def chatid(self):
        return self.channel['id']

    @property
    def channelid(self):
        if isinstance(self.channel, dict):
            return self.channel['id']
        else:
            return self.channel

    @property
    def userid(self):
        if isinstance(self.user, dict):
            return self.user['id']
        else:
            return self.user

    @property
    def user_full_name(self):
        fullname = " ".join((self.user['first_name'],
                             self.user.get('last_name', ''))).strip()
        return fullname

    @property
    def user_name(self):
        return self.user['first_name']

    def describeUser(self):
        if not isinstance(self.user, dict):
            return self.user

        user = self.user_full_name
        try:
            user += ' (@{})'.format(self.user['username'])
        except KeyError:
            pass

        if isinstance(self.channel, dict) and \
                self.channel['id'] != self.user['id']:
            chat_title = self.channel.get('title')
            if chat_title: user += " on '{}'".format(chat_title)

        return user

    _scared_users = {}

    _stop_phrase = (
        ("👹  You shall not pass!!!  👹", 'CAADAgAD1AIAAmMr4gkRoBV--rBVehYE'),
        ("👾  Do it not, you can!  👾", 'CAADAgADAxgAAkKvaQABG4A6r70tTawWBA')
    )

    @defer.inlineCallbacks
    def access_denied(self, *args):
        uid = self.user['id']
        if uid == self.channel['id']:
            text, sticker = random.choice(self._stop_phrase)
            self.send("{}".format(text))
            now = util.now()
            # clean users scared some time ago
            horizon = now - 600
            for u,t in list(self._scared_users.items()):
                if t < horizon:
                    del self._scared_users[u]
            if self._scared_users.get(uid) is None:
                self._scared_users[uid] = now
                self.bot.send_sticker(uid, sticker)
        else:
            fullname = self.user_full_name
            self.send("⛔  Sorry {}, you are not allowed do this!  ⛔"
                      .format(fullname))

    def query_button(self, caption, payload):
        if isinstance(payload, str) and len(payload) < 64:
            return {'text': caption, 'callback_data': payload}
        n = 0
        while True:
            key = hash(payload)
            cached = self.bot.query_cache.get(key)
            if cached is None:
                self.bot.query_cache[key] = payload
                break
            elif cached == payload:
                break
            n += 1
        return {'text': caption, 'callback_data': key}

    @defer.inlineCallbacks
    def command_START(self, args, **kwargs):
        yield self.command_HELLO(args)
        self.reactor.callLater(0.2, self.command_HELP, '')

    def command_NAY(self, args, **kwargs):
        """forget the current command"""
        partial = kwargs.get('partial')
        if partial:
            self.send("Cancelling command '{}'.".format(self.partial))
        self.partial = ''
    command_NAY.usage = "nay - forget the command we are currently discussing"

    @Contact.overrideCommand
    def command_COMMANDS(self, args, **kwargs):
        if args.lower() == 'botfather':
            lp = len(self.bot.commandPrefix)
            commands = self.build_commands()
            results = []
            for command in commands:
                command = command[lp:]
                if command == 'start':
                    continue
                meth = self.getCommandMethod(command, True)
                doc = getattr(meth, '__doc__', None)
                if not doc:
                    doc = command
                results.append("{} - {}".format(command, doc))
            if results:
                self.send(results)
        else:
            return super().command_COMMANDS(args)

    @defer.inlineCallbacks
    @Contact.overrideCommand
    def command_DANCE(self, args, **kwargs):
        chat = self.channel['id']
        msg = yield self.bot.send_message(chat, "**<(^.^<)**")
        if msg is not None:
            mid = msg['message_id']
            self.reactor.callLater(1.0, self.bot.edit_message, chat, mid, "**<(^.^)>**")
            self.reactor.callLater(2.0, self.bot.edit_message, chat, mid, "**(>^.^)>**")
            self.reactor.callLater(2.5, self.bot.edit_message, chat, mid, "**(7^.^)7**")
            self.reactor.callLater(4.0, self.bot.edit_message, chat, mid, "**(>^.^<)**")
            self.reactor.callLater(5.0, self.bot.delete_message, chat, mid)
            self.reactor.callLater(5.5, self.bot.send_sticker, chat, random.choice((
                'CAADAgAD9wEAAsoDBgtCnbBFfI8M_BYE',
                'CAADAgADQQIAArnzlwuD160COMLwKRYE')))

    @defer.inlineCallbacks
    def command_GETID(self, args, **kwargs):
        """get user and chat ID"""
        if self.userid == self.chatid:
            self.send("Your ID is {}.".format(self.userid))
        else:
            yield self.send("{}, your ID is {}.".format(self.user_name, self.userid))
            self.send("This {} ID is {}.".format(self.channel['type'], self.chatid))
    command_GETID.usage = "getid - get user and chat ID that can be put in the master configuration file"

    @defer.inlineCallbacks
    def get_running_builders(self):
        builders = []
        for bdict in (yield self.getAllBuilders()):
            if (yield self.getRunningBuilds(bdict['builderid'])):
                builders.append(bdict['name'])
        return builders

    @defer.inlineCallbacks
    @Contact.overrideCommand
    def command_WATCH(self, args, **kwargs):
        if args:
            super().command_WATCH(args)
        else:
            builders = yield self.get_running_builders()
            if builders:
                keyboard = [
                    [self.query_button("🔎 " + b, '/watch {}'.format(b))]
                    for b in builders
                ]
                self.bot.send_message(self.channel,
                                      "Which builder do you want to watch?",
                                      reply_markup={
                                          'inline_keyboard': keyboard
                                      })
            else:
                self.send("There are no currently running builds.")

    def list_notified_events(self):
        if self.chatid == self.userid:
            text = "You will be notified about "
        else:
            text = "In this group, {} will be notified about "\
                .format(self.user_full_name)
        if not self.notify_events:
            text += "no events."
        else:
            text += "the following events: " + ", ".join(sorted(
                "_{}_".format(n) for n in self.notify_events)) + "."
        self.send(text)

    @Contact.overrideCommand
    def command_NOTIFY(self, args, tmessage, tquery=None, **kwargs):
        if args:
            super().command_NOTIFY(args)
            if not tquery:
                return

        if args == 'list':
            self.bot.delete_message(self.chatid, tquery['message']['message_id'])
            keyboard = None
        else:
            keyboard = [
                [
                    self.query_button("{} {}".format(e.capitalize(), '🔔' if e in self.notify_events else '🔕'),
                                      '/notify {}-quiet {}'.format('off' if e in self.notify_events else 'on', e))
                    for e in evs
                ]
                for evs in (('started', 'finished'), ('success', 'failure'), ('warnings', 'exception'),
                            ('problem', 'recovery'), ('worse', 'better'))
            ] + [[self.query_button("Done", '/notify list')]]

        if tquery:
            self.bot.edit_keyboard(self.chatid, tquery['message']['message_id'], keyboard)
        else:
            if self.chatid == self.userid:
                self.bot.send_message(self.channel, "This is a list of your notifications. "
                                                    "Click to turn them on/off:",
                                      reply_markup={'inline_keyboard': keyboard})
            else:
                username = self.user.get('username')
                username = " ({})".format(username) if username is not None else ''
                self.bot.send_message(self.channel, "This is a list of notifications for {}. "
                                                    "You{} can click to turn them on/off:"
                                                    .format(self.user_full_name, username),
                                      reply_markup={'inline_keyboard': keyboard})

    @Contact.overrideCommand
    def command_FORCE(self, args, **kwargs):
        super().command_FORCE(args)

    @defer.inlineCallbacks
    @Contact.overrideCommand
    def command_STOP(self, args, **kwargs):
        argv = self.splitArgs(args)
        if len(argv) >= 3 or \
                len(argv) > 0 and argv[0] != 'build':
            super().command_STOP(args)
            return
        argv = argv[1:]
        if len(argv) == 0:
            builders = yield self.get_running_builders()
            if builders:
                keyboard = [
                    [self.query_button("🚫 " + b, '/stop build {}'.format(b))]
                    for b in builders
                ]
                self.bot.send_message(self.channel,
                                      "Select builder to stop...",
                                      reply_markup={
                                          'inline_keyboard': keyboard
                                      })
        else:  # len(argv) == 1
            self.partial = '/stop ' + args + ' '
            kwargs = {}
            if self.userid != self.chatid:
                username = self.user.get('username', '')
                if username:
                    voc = " @{}, now".format(username)
                    kwargs['reply_markup'] = {
                        'force_reply': True,
                        'selective': True
                    }
                else:
                    voc = ", now reply to this message and"
            else:
                voc = ", now"
            self.bot.send_message(self.channel,
                                  "Great{} give me the reason to stop build on `{}`..."
                                  .format(voc, argv[0]), **kwargs)


    @Contact.overrideCommand
    def command_SHUTDOWN(self, args, **kwargs):
        if args:
            return super().command_SHUTDOWN(args)
        shuttingDown = self.master.botmaster.shuttingDown
        keyboard = [[
             self.query_button("🔙 Stop Shutdown", '/shutdown stop')
             if shuttingDown else
             self.query_button("↘️ Begin Shutdown", '/shutdown start'),
             self.query_button("‼️ Shutdown Now", '/shutdown now')
        ]]
        text = "Buildbot is currently shutting down.\n\n" if shuttingDown else ""
        self.bot.send_message(self.channel,
                              text + "What do you want to do?",
                              reply_markup={
                                  'inline_keyboard': keyboard
                              })


class TelegramBotResource(StatusBot, resource.Resource):
    """
    I represent the buildbot to
    a some web-hooks based chat.
    """

    contactClass = TelegramContact
    commandPrefix = '/'

    query_cache = {}

    @property
    def commandSuffix(self):
        if self.nickname is not None:
            return '@' + self.nickname
        return None

    def __init__(self, token, outgoing_http, chat_ids, *args, **kwargs):
        StatusBot.__init__(self, *args, **kwargs)
        resource.Resource.__init__(self)

        self.http_client = outgoing_http
        self.token = token

        for c in chat_ids:
            self.getContact(channel=c)

        self.nickname = None

    def getContact(self, user=None, channel=None):
        """ get a Contact instance for ``user`` on ``channel`` """
        uid = None if user is None else \
            user['id'] if isinstance(user, dict) else user
        cid = None if channel is None else \
            channel['id'] if isinstance(channel, dict) else channel
        try:
            contact = self.contacts[(cid, uid)]
            if isinstance(user, dict):
                if isinstance(contact.user, dict):
                    contact.user.update(user)
                else:
                    contact.user = user
            if isinstance(channel, dict):
                if isinstance(contact.channel, dict):
                    contact.channel.update(channel)
                else:
                    contact.channel = channel
            return contact
        except KeyError:
            new_contact = self.contactClass(self, user=user, channel=channel)
            self.contacts[(cid, uid)] = new_contact
            new_contact.setServiceParent(self)
            return new_contact

    def render_GET(self, request):
        return self.render_POST(request)

    def render_POST(self, request):
        try:
            d = self.process_incoming(request)
        except Exception:
            d = defer.fail()

        def ok(_):
            request.setResponseCode(202)
            request.finish()

        def err(why):
            log.err(why, "processing telegram request")
            request.setResponseCode(500)
            request.finish()

        d.addCallbacks(ok, err)

        return server.NOT_DONE_YET

    def get_update(self, request):
        content = request.content.read()
        content = bytes2unicode(content)
        content_type = request.getHeader(b'Content-Type')
        content_type = bytes2unicode(content_type)
        if content_type is not None and \
                content_type.startswith('application/json'):
            update = json.loads(content)
        else:
            raise ValueError('Unknown content type: {}'
                             .format(content_type))
        return update

    def process_incoming(self, request):
        update = self.get_update(request)

        data = {}

        message = update.get('message')
        if message is None:
            query = update.get('callback_query')
            if query is None:
                self.log('telegram bot: no message')
                return defer.succeed('no message')
            original_message = query.get('message', {})
            data = query.get('data', 0)
            try:
                data = self.query_cache[int(data)]
            except ValueError:
                text, data, notify = data, {}, None
            except KeyError:
                text, data, notify = None, {}, "Sorry, button is no longer valid!"
                if original_message:
                    try:
                        self.edit_keyboard(
                            original_message['chat']['id'],
                            original_message['message_id'])
                    except KeyError:
                        pass
            else:
                if isinstance(data, dict):
                    data = data.copy()
                    text = data.pop('command')
                    try:
                        notify = data.pop('notify')
                    except KeyError:
                        notify = None
                else:
                    text, data, notify = data, {}, None
            data['tquery'] = query
            self.answer_query(query['id'], notify)
            message = {
                'from': query['from'],
                'chat': original_message.get('chat'),
                'text': text,
            }
            if 'reply_to_message' in original_message:
                message['reply_to_message'] = original_message['reply_to_message']

        user = message.get('from')
        if user is None:
            self.log('no user in incoming telegram message')
            return defer.succeed('no user')

        chat = message.get('chat')
        if chat is None:
            self.log('no chat in telegram message')
            return defer.succeed('no chat in the message')

        text = message.get('text')
        if not text:
            return defer.succeed('no text in the message')

        contact = self.getContact(user=user, channel=chat)
        data['tmessage'] = message
        if contact.partial:
            data['partial'] = contact.partial
        if text.startswith(self.commandPrefix):
            d = contact.handleMessage(text, **data)
        else:
            d = contact.handleMessage(contact.partial + text, **data)
        return d

    @defer.inlineCallbacks
    def _post(self, path, **kwargs):
        try:
            res = yield self.http_client.post(path, **kwargs)
            ans = yield res.json()
            if not ans.get('ok'):
                raise ValueError("({}) {}".format(res.code, ans.get('description')))
            else:
                return ans.get('result')
        except Exception as err:
            self.log("ERROR: cannot send '{}' to telegram: {}".format(path, err))

    def set_webhook(self, url, certificate=None):
        self.log("Setting up webhook to: {}".format(url))
        if not certificate:
            self._post('/setWebhook', json=dict(url=url))
        else:
            if not hasattr(certificate, 'read'):
                certificate = io.BytesIO(unicode2bytes(certificate))
                certificate.name = 'certificate.pem'
            self._post('/setWebhook', data=dict(url=url),
                       files=dict(certificate=certificate))

    @defer.inlineCallbacks
    def set_nickname(self):
        res = yield self._post('/getMe')
        if res:
            self.nickname = res.get('username')

    @defer.inlineCallbacks
    def answer_query(self, query_id, notify=None):
        params = dict(callback_query_id=query_id)
        if notify is not None:
            params.update(dict(text=notify))
        return (yield self._post('/answerCallbackQuery', json=params))

    @defer.inlineCallbacks
    def send_message(self, channel, message, parse_mode='Markdown', **kwargs):
        chat = channel['id'] if isinstance(channel, dict) else channel
        params = dict(chat_id=chat, text=message)
        if parse_mode is not None:
            params['parse_mode'] = parse_mode
        params.update(kwargs)
        return (yield self._post('/sendMessage', json=params))

    @defer.inlineCallbacks
    def edit_message(self, chat, msg, message, **kwargs):
        params = dict(chat_id=chat, message_id=msg, text=message)
        params.update(kwargs)
        return (yield self._post('/editMessageText', json=params))

    @defer.inlineCallbacks
    def edit_keyboard(self, chat, msg, keyboard=None):
        params = dict(chat_id=chat, message_id=msg)
        if keyboard is not None:
            params['reply_markup'] = {'inline_keyboard': keyboard}
        return (yield self._post('/editMessageReplyMarkup', json=params))

    @defer.inlineCallbacks
    def delete_message(self, chat, msg):
        params = dict(chat_id=chat, message_id=msg)
        return (yield self._post('/deleteMessage', json=params))

    @defer.inlineCallbacks
    def send_sticker(self, chat, sticker, **kwargs):
        params = dict(chat_id=chat, sticker=sticker)
        params.update(kwargs)
        return (yield self._post('/sendSticker', json=params))


class TelegramBot(service.BuildbotService):
    name = "TelegramBot"

    in_test_harness = False

    compare_attrs = ["bot_token", "chat_ids", "authz",
                     "tags", "notify_events",
                     "showBlameList", "useRevisions",
                     "certificate"]
    secrets = ["bot_token"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.www = get_plugins('www', None, load_now=True)
        self.bot = None

    def checkConfig(self, bot_token, chat_ids=None, authz=None,
                    bot_username=None, tags=None, notify_events=None,
                    showBlameList=True, useRevisions=False,
                    certificate=None, **kwargs
                    ):

        if authz is not None:
            for acl in authz.values():
                if not isinstance(acl, (list, tuple, bool)):
                    config.error("authz values must be bool or a list of user ids")

        if isinstance(certificate, io.TextIOBase):
            config.error("certificate file must be open in binary mode")

    def _get_http(self, bot_token):
        base_url = "https://api.telegram.org/bot" + bot_token
        return httpclientservice.HTTPClientService.getService(
            self.master, base_url)

    @defer.inlineCallbacks
    def reconfigService(self, bot_token, chat_ids=None, authz=None,
                        bot_username=None, tags=None, notify_events=None,
                        showBlameList=True, useRevisions=False,
                        certificate=None, **kwargs
                        ):
        # need to stash these so we can detect changes later
        self.bot_token = bot_token
        if chat_ids is None:
            chat_ids = []
        self.chat_ids = chat_ids
        self.authz = authz
        self.useRevisions = useRevisions
        self.tags = tags
        if notify_events is None:
            notify_events = set()
        self.notify_events = notify_events
        self.certificate = certificate

        # This function is only called in case of reconfig with changes
        # We don't try to be smart here. Just restart the bot if config has
        # changed.

        if 'base' not in self.www:
            raise RuntimeError("could not find buildbot-www; is it installed?")
        root = self.www.get('base').resource

        http = yield self._get_http(bot_token)

        if self.bot is not None:
            self.bot.stopService()
            root.delEntity(unicode2bytes('bot' + self.bot.token))

        self.bot = TelegramBotResource(bot_token, http, chat_ids, authz,
                                       tags=tags, notify_events=notify_events,
                                       useRevisions=useRevisions,
                                       showBlameList=showBlameList)
        self.bot.setServiceParent(self)
        bot_path = 'bot' + bot_token
        root.putChild(unicode2bytes(bot_path), self.bot)
        url = bytes2unicode(self.master.config.buildbotURL)
        if not url.endswith('/'): url += '/'
        self.bot.set_webhook(url + bot_path, certificate)
        if bot_username is None:
            yield self.bot.set_nickname()
        else:
            self.bot.nickname = bot_username
