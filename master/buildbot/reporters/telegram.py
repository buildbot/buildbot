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
import shlex

from twisted.internet import defer
from twisted.internet import task
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
from buildbot.reporters.words import Channel
from buildbot.reporters.words import Contact
from buildbot.reporters.words import StatusBot
from buildbot.reporters.words import UsageError
from buildbot.schedulers.forcesched import CollectedValidationError
from buildbot.util import bytes2unicode
from buildbot.util import httpclientservice
from buildbot.util import service
from buildbot.util import unicode2bytes


class TelegramChannel(Channel):

    def __init__(self, bot, channel):
        if isinstance(channel, dict):
            super().__init__(bot, channel['id'])
            self.chat = channel
        else:
            super().__init__(bot, channel)
            self.chat = {'id': channel}

    def __getitem__(self, item):
        return self.chat[item]

    def get(self, item, default=None):
        return self.chat.get(item, default)

    def update(self, src):
        self.chat.update(src)

    def list_notified_events(self):
        if self.notify_events:
            self.send("The following events are being notified:\n{}"
                      .format("\n".join(sorted(
                          "🔔 **{}**".format(n) for n in self.notify_events))))
        else:
            self.send("🔕 No events are being notified.")


def collect_fields(fields):
    for field in fields:
            if field['fullName']:
                yield field
            if 'fields' in field:
                yield from collect_fields(field['fields'])


class TelegramContact(Contact):

    def __init__(self, bot, user=None, channel=None):
        super().__init__(bot, user, channel)
        self.template = None

    @property
    def chatid(self):
        return self.channel.id

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

        if self.channel.id != self.userid:
            chat_title = self.channel.get('title')
            if chat_title: user += " on '{}'".format(chat_title)

        return user

    _scared_users = {}

    _stop_phrase = (
        ("👾  Do it not, you can!  👾", 'CAADAgADAxgAAkKvaQABG4A6r70tTawWBA'),
        ("👹  You shall not pass!!!  👹", 'CAADAgAD1AIAAmMr4gkRoBV--rBVehYE'),
    )

    @defer.inlineCallbacks
    def access_denied(self, *args, tmessage, **kwargs):
        uid = self.user['id']
        if uid == self.channel['id']:
            text, sticker = random.choice(self._stop_phrase)
            now = util.now()
            # clean users scared some time ago
            horizon = now - 120
            for u,t in list(self._scared_users.items()):
                if t < horizon:
                    del self._scared_users[u]
            if self._scared_users.get(uid) is None:
                self._scared_users[uid] = now
                yield self.send(
                    "{}".format(text),
                    reply_to_message_id=tmessage['message_id'])
                yield self.bot.send_sticker(uid, sticker)
                return

        self.send(
            "⛔  ACCESS DENIED  ⛔\n\n" +
            random.choice((
                "You are simply not allowed to to this!",
                "Go outside and relax...",
                "Please proceed to the extermination zone →",
                "This incident has ben reported to NSA!",
            )), reply_to_message_id=tmessage['message_id'])

    def query_button(self, caption, payload):
        if isinstance(payload, str) and len(payload) < 64:
            return {'text': caption, 'callback_data': payload}
        key = hash(repr(payload))
        while True:
            cached = self.bot.query_cache.get(key)
            if cached is None:
                self.bot.query_cache[key] = payload
                break
            elif cached == payload:
                break
            key += 1
        return {'text': caption, 'callback_data': key}

    @defer.inlineCallbacks
    def command_START(self, args, **kwargs):
        yield self.command_HELLO(args)
        self.bot.reactor.callLater(0.2, self.command_HELP, '')

    def command_NAY(self, args, tmessage, **kwargs):
        """forget the current command"""
        replied_message = tmessage.get('reply_to_message')
        if replied_message:
            if 'reply_markup' in replied_message:
                self.bot.edit_keyboard(self.channel.id,
                                       replied_message['message_id'])
        if self.userid == self.channel.id:
            self.send("Never mind...")
        else:
            self.send("Never mind, {}...".format(self.user_name))
    command_NAY.usage = "nay - never mind the command we are currently discussing"

    @Contact.overrideCommand
    def command_COMMANDS(self, args, **kwargs):
        if args.lower() == 'botfather':
            lp = len(self.bot.commandPrefix)
            commands = self.build_commands()
            response = []
            for command in commands:
                command = command[lp:]
                if command == 'start':
                    continue
                meth = self.getCommandMethod(command, True)
                doc = getattr(meth, '__doc__', None)
                if not doc:
                    doc = command
                response.append("{} - {}".format(command, doc))
            if response:
                self.send('\n'.join(response))
        else:
            return super().command_COMMANDS(args)

    @defer.inlineCallbacks
    @Contact.overrideCommand
    def command_DANCE(self, args, **kwargs):
        chat = self.channel['id']
        msg = yield self.send( "**<(^.^<)**")
        if msg is not None:
            mid = msg['message_id']
            self.bot.reactor.callLater(1.0, self.bot.edit_message, chat, mid, "**<(^.^)>**")
            self.bot.reactor.callLater(2.0, self.bot.edit_message, chat, mid, "**(>^.^)>**")
            self.bot.reactor.callLater(2.5, self.bot.edit_message, chat, mid, "**(7^.^)7**")
            self.bot.reactor.callLater(4.0, self.bot.edit_message, chat, mid, "**(>^.^<)**")
            self.bot.reactor.callLater(5.0, self.bot.delete_message, chat, mid)
            self.bot.reactor.callLater(5.5, self.bot.send_sticker, chat, random.choice((
                'CAADAgAD9wEAAsoDBgtCnbBFfI8M_BYE',
                'CAADAgADQQIAArnzlwuD160COMLwKRYE')))

    @defer.inlineCallbacks
    def command_GETID(self, args, **kwargs):
        """get user and chat ID"""
        if self.userid == self.chatid:
            self.send("Your ID is {}.".format(self.userid))
        else:
            yield self.send("{}, your ID is {}.".format(self.user_name, self.userid))
            self.send("This {} ID is {}.".format(self.channel.get('type', "group"), self.chatid))
    command_GETID.usage = "getid - get user and chat ID that can be put in the master configuration file"

    @defer.inlineCallbacks
    @Contact.overrideCommand
    def command_LIST(self, args, **kwargs):
        args = self.splitArgs(args)
        if not args:
                keyboard = [
                    [self.query_button("👷️ Builders", '/list builders')],
                    [self.query_button("⚙ Workers", '/list workers')],
                    [self.query_button("📄 Changes", '/list changes')],
                ]
                self.send("What do you want to list?",
                          reply_markup={'inline_keyboard': keyboard})

        elif args[0] == 'builders':
            bdicts = yield self.bot.getAllBuilders()
            online_builderids = yield self.bot.getOnlineBuilders()

            response = ["I found the following **builders**:"]
            for bdict in bdicts:
                response.append("`{}`".format(bdict['name']))
                if bdict['builderid'] not in online_builderids:
                    response[-1] += " ❌"
            self.send('\n'.join(response))

        elif args[0] == 'workers':
            workers = yield self.master.data.get(('workers',))

            response = ["I found the following **workers**:"]
            for worker in workers:
                response.append("`{}`".format(worker['name']))
                if not worker['configured_on']:
                    response[-1] += " ❌"
                if not worker['connected_to']:
                    response[-1] += " ⚠️"
            self.send('\n'.join(response))

        else:
            try:
                num = int(args[0])
            except ValueError:
                num = 5
            else:
                del args[0]

            if args[0] == 'changes':
                changes = yield self.master.db.changes.getRecentChanges(num)

                response = ["I found the following recent **changes**:"]
                for change in reversed(changes):
                    change['comment'] = change['comments'].split('\n')[0]
                    change['date'] = change['when_timestamp'].strftime('%Y-%m-%d %H:%M')
                    response.append(
                        "[{comment}]({revlink})\n"
                        "_Author_: {author}\n"
                        "_Date_: {date}\n"
                        "_Repository_: {repository}\n"
                        "_Branch_: {branch}\n"
                        "_Revision_: {revision}\n".format(**change))
                self.send('\n\n'.join(response))

    @defer.inlineCallbacks
    def get_running_builders(self):
        builders = []
        for bdict in (yield self.bot.getAllBuilders()):
            if (yield self.bot.getRunningBuilds(bdict['builderid'])):
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
                self.send("Which builder do you want to watch?",
                          reply_markup={'inline_keyboard': keyboard})
            else:
                self.send("There are no currently running builds.")

    @Contact.overrideCommand
    def command_NOTIFY(self, args, tquery=None, **kwargs):
        if args:
            want_list = args == 'list'
            if want_list and tquery:
                self.bot.delete_message(self.chatid, tquery['message']['message_id'])

            super().command_NOTIFY(args)

            if want_list or not tquery:
                return

        keyboard = [
            [
                self.query_button("{} {}".format(e.capitalize(),
                                                 '🔔' if e in self.channel.notify_events else '🔕'),
                                  '/notify {}-quiet {}'.format(
                                      'off' if e in self.channel.notify_events else 'on', e))
                for e in evs
            ]
            for evs in (('started', 'finished'), ('success', 'failure'), ('warnings', 'exception'),
                        ('problem', 'recovery'), ('worse', 'better'), ('cancelled', 'worker'))
        ] + [[self.query_button("Hide...", '/notify list')]]

        if tquery:
            self.bot.edit_keyboard(self.chatid, tquery['message']['message_id'], keyboard)
        else:
            self.send("Here are available notifications and their current state. "
                      "Click to turn them on/off.",
                      reply_markup={'inline_keyboard': keyboard})

    def ask_for_reply(self, prompt, greeting='Ok'):
        kwargs = {}
        if self.userid != self.chatid:
            username = self.user.get('username', '')
            if username:
                if greeting:
                    prompt = "{} @{}, now {}...".format(greeting, username, prompt)
                else:
                    prompt = "@{}, now {}...".format(username, prompt)
                kwargs['reply_markup'] = {
                    'force_reply': True,
                    'selective': True
                }
            else:
                if greeting:
                    prompt = "{}, now reply to this message and {}...".format(greeting, prompt)
                else:
                    prompt = "Reply to this message and {}...".format(prompt)
        else:
            if greeting:
                prompt = "{}, now {}...".format(greeting, prompt)
            else:
                prompt = prompt[0].upper() + prompt[1:] + "..."
            kwargs['reply_markup'] = {
                'force_reply': True
            }
        self.send(prompt, **kwargs)

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
                self.send("Select builder to stop...",
                          reply_markup={'inline_keyboard': keyboard})
        else:  # len(argv) == 1
            self.template = '/stop ' + args + ' {}'
            self.ask_for_reply("give me the reason to stop build on `{}`".format(argv[0]))

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
        self.send(text + "What do you want to do?",
                  reply_markup={'inline_keyboard': keyboard})

    @defer.inlineCallbacks
    def command_FORCE(self, args, tquery=None, partial=None, **kwargs):
        """force a build"""

        forceschedulers = yield self.master.data.get(('forceschedulers',))
        forceschedulers = dict((s['name'], s) for s in forceschedulers)

        argv = self.splitArgs(args)

        try:
            sched = argv[0]
        except IndexError:
            if len(forceschedulers) == 1:
                sched = next(iter(forceschedulers))
            else:
                keyboard = [
                    [self.query_button(s['label'], '/force {}'.format(s['name']))]
                    for s in forceschedulers.values()
                ]
                self.send("Which force scheduler do you want to activate?",
                          reply_markup={'inline_keyboard': keyboard})
                return
        else:
            if sched in forceschedulers:
                del argv[0]
            elif len(forceschedulers) == 1:
                sched = next(iter(forceschedulers))
        try:
            scheduler = forceschedulers[sched]
        except KeyError:
            raise UsageError("Try '/force' and follow the instructions"
                             " (no force scheduler {})".format(sched))

        try:
            task = argv.pop(0)
        except IndexError:
            task = 'config'

        if tquery and task != 'config':
            self.bot.edit_keyboard(self.chatid, tquery['message']['message_id'])

        if len(argv) == 0:
            keyboard = [
                [self.query_button(b, '/force {} {} {}'.format(sched, task, b))]
                for b in scheduler['builder_names']
            ]
            self.send("Which builder do you want to start?",
                      reply_markup={'inline_keyboard': keyboard})
            return

        if task == 'ask':
            try:
                what = argv.pop(0)
            except IndexError:
                raise UsageError("Try '/force' and follow the instructions")
        else:
            what = None # silence PyCharm warnings

        bldr = argv.pop(0)
        if bldr not in scheduler['builder_names']:
            raise UsageError("Try '/force' and follow the instructions (`{}` not configured for _{}_ scheduler)"
                             .format(bldr, scheduler['label']))

        try:
            params = dict(arg.split('=', 1) for arg in argv)
        except ValueError as err:
            raise UsageError("Try '/force' and follow the instructions ({})".format(err))

        all_fields = list(collect_fields(scheduler['all_fields']))
        required_params = [f['fullName'] for f in all_fields
                           if f['required'] and f['fullName'] not in ('username', 'owner')]
        missing_params = [p for p in required_params if p not in params]

        if task == 'build':
            #TODO This should probably be moved to the upper class,
            # however, it will change the force command totally

            try:
                # sched = argv[0]
                # if sched in data:
                #     del data[0]
                # elif len(data) == 1:
                #     sched = next(iter(data))
                # else:
                #     raise ValueError(sched)
                # builder_name = argv.pop(0)

                if missing_params:
                    # raise UsageError
                    task = 'config'
                else:
                    builder = yield self.bot.getBuilder(buildername=bldr)
                    try:
                        scheduler = self.master.config.schedulers[sched]
                    except KeyError:
                        raise ValueError("There is no force scheduler '{}'".format(sched))
                    try:
                        yield scheduler.force(builderid=builder['builderid'],
                                              owner=self.describeUser(),
                                              **params)
                    except CollectedValidationError as err:
                        raise ValueError(err.errors)
                    else:
                        self.send("Force build successfully requested.")
                    return

            except (IndexError, ValueError) as err:
                raise UsageError("Try '/force' and follow the instructions ({})".format(err))

        if task == 'config':

            msg = "{}, you are about to start a new build on `{}`!"\
                .format(self.user_full_name, bldr)

            keyboard = []
            args = ' '.join(shlex.quote("{}={}".format(*p)) for p in params.items())

            fields = [f for f in all_fields if f['type'] != 'fixed'
                      and f['fullName'] not in ('username', 'owner')]

            if fields:
                msg += "\n\nThe current build parameters are:"
                for field in fields:
                    if field['type'] == 'nested':
                        msg += "\n{}".format(field['label'])
                    else:
                        field_name = field['fullName']
                        value = params.get(field_name, field['default']).strip()
                        msg += "\n    {} `{}`".format(field['label'], value)
                        if value: key = "Change "
                        else: key = "Set "
                        key += field_name.replace('_', ' ').title()
                        if field_name in missing_params:
                            key = "⚠️ " + key
                            msg += " ⚠️"
                        keyboard.append(
                            [self.query_button(key, '/force {} ask {} {} {}'
                                               .format(sched, field_name, bldr, args))]
                        )

            msg += "\n\nWhat do you want to do?"
            if missing_params:
                msg += " You must set values for all parameters marked with ⚠️"

            if not missing_params:
                keyboard.append(
                    [self.query_button("🚀 Start Build", '/force {} build {} {}'
                                       .format(sched, bldr, args))],
                )

            self.send(msg, reply_markup={'inline_keyboard': keyboard})

        elif task == 'ask':
            prompt = "enter the new value for the " + what.replace('_', ' ').lower()
            args = ' '.join(shlex.quote("{}={}".format(*p)) for p in params.items()
                            if p[0] != what)
            self.template = '/force {} config {} {} {}={{}}'.format(sched, bldr, args, what)
            self.ask_for_reply(prompt, '')

        else:
            raise UsageError("Try '/force' and follow the instructions")

    command_FORCE.usage = "force - Force a build"


class TelegramStatusBot(StatusBot):
    """
    I represent the buildbot to
    a some web-hooks based chat.
    """

    contactClass = TelegramContact
    channelClass = TelegramChannel
    commandPrefix = '/'

    offline_string = "offline ❌"
    idle_string = "idle 💤"
    running_string = "running 🌀:"

    query_cache = {}

    @property
    def commandSuffix(self):
        if self.nickname is not None:
            return '@' + self.nickname
        return None

    def __init__(self, token, outgoing_http, chat_ids, *args, retry_delay=30, **kwargs):
        super().__init__(*args, **kwargs)

        self.http_client = outgoing_http
        self.retry_delay = retry_delay
        self.token = token

        self.chat_ids = chat_ids

        self.nickname = None

    def startService(self):
        super().startService()
        for c in self.chat_ids:
            channel = self.getChannel(c)
            channel.add_notification_events(self.notify_events)
        self.loadNotifyEvents()

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

    def getContact(self, user, channel=None):
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
                contact.channel.update(channel)
            return contact
        except KeyError:
            new_contact = self.contactClass(self, user=user, channel=channel)
            self.contacts[(cid, uid)] = new_contact
            return new_contact

    def getChannel(self, channel):
        cid = channel['id'] if isinstance(channel, dict) else channel
        try:
            return self.channels[cid]
        except KeyError:
            new_channel = self.channelClass(self, channel)
            self.channels[cid] = new_channel
            new_channel.setServiceParent(self)
            return new_channel

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

    def process_update(self, update):
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
        template, contact.template = contact.template, None
        if text.startswith(self.commandPrefix):
            d = contact.handleMessage(text, **data)
        else:
            if template:
                text = template.format(shlex.quote(text))
            d = contact.handleMessage(text, **data)
        return d

    @defer.inlineCallbacks
    def _post(self, path, **kwargs):
        try:
            res = yield self.http_client.post(path, **kwargs)
            ans = yield res.json()
            if not ans.get('ok'):
                raise ValueError("[{}] {}".format(res.code, ans.get('description')))
        except AssertionError as err:
            # just for tests
            raise err
        except Exception as err:
            self.log("ERROR: cannot send telegram request {}: {}".format(path, err))
        else:
            return ans.get('result', True)

    @defer.inlineCallbacks
    def _post_until_success(self, path, **kwargs):
        logme = True
        while True:
            try:
                res = yield self.http_client.post(path, **kwargs)
                ans = yield res.json()
                if not ans.get('ok'):
                    self.log("ERROR: cannot send telegram request {}: "
                             "[{}] {}".format(path, res.code, ans.get('description')))
                    return
            except AssertionError as err:
                # just for tests
                raise err
            except Exception as err:
                msg = "ERROR: cannot send telegram request {} (will try again): {}".format(path, err)
                if logme:
                    self.log(msg)
                    logme = False
                yield task.deferLater(self.reactor, self.retry_delay, lambda: None)
            else:
                return ans.get('result', True)

    @defer.inlineCallbacks
    def set_nickname(self):
        res = yield self._post_until_success('/getMe')
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
        chat = channel['id'] if isinstance(channel, (dict, TelegramChannel)) else channel
        params = dict(chat_id=chat, text=message)
        if parse_mode is not None:
            params['parse_mode'] = parse_mode
        params.update(kwargs)
        return (yield self._post('/sendMessage', json=params))

    @defer.inlineCallbacks
    def edit_message(self, chat, msg, message, parse_mode='Markdown', **kwargs):
        params = dict(chat_id=chat, message_id=msg, text=message)
        if parse_mode is not None:
            params['parse_mode'] = parse_mode
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


class TelegramBotResource(TelegramStatusBot, resource.Resource):

    def __init__(self, *args, **kwargs):
        TelegramStatusBot.__init__(self, *args, **kwargs)
        resource.Resource.__init__(self)

    def render_GET(self, request):
        return self.render_POST(request)

    def render_POST(self, request):
        try:
            d = self.process_webhook_request(request)
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

    def process_webhook_request(self, request):
        update = self.get_update(request)
        return self.process_update(update)

    def set_webhook(self, url, certificate=None):
        if not certificate:
            self.log("Setting up webhook to: {}".format(url))
            self._post_until_success('/setWebhook', json=dict(url=url))
        else:
            self.log("Setting up webhook to: {} (custom certificate)".format(url))
            filename = getattr(certificate, 'name', "certificate.pem")
            if hasattr(certificate, 'read'):
                # we may be trying several times, so we need to store the certificate content
                certificate = certificate.read()
            certificate = io.BytesIO(unicode2bytes(certificate))
            certificate.name = filename
            self._post_until_success('/setWebhook', data=dict(url=url),
                                     files=dict(certificate=certificate))


class TelegramPollingBot(TelegramStatusBot):
    name = "TelegramPollingBot"

    def __init__(self, *args, poll_timeout=120, **kwargs):
        super().__init__(*args, **kwargs)
        self.poll_timeout = poll_timeout

    def startService(self):
        super().startService()
        self.do_polling()

    @defer.inlineCallbacks
    def do_polling(self):
        yield self._post_until_success('/deleteWebhook')
        offset = 0
        kwargs = {'json': {'timeout': self.poll_timeout}}
        logme = True
        while self.running:
            if offset:
                kwargs['json']['offset'] = offset
            try:
                res = yield self.http_client.post('/getUpdates',
                                                  timeout=self.poll_timeout+5,
                                                  **kwargs)
                ans = yield res.json()
                if not ans.get('ok'):
                    raise ValueError("[{}] {}".format(res.code, ans.get('description')))
                else:
                    updates = ans.get('result')
            except Exception as err:
                msg = "ERROR: cannot send telegram request /getUpdates (will try again): {}".format(err)
                if logme:
                    self.log(msg)
                    logme = False
                yield task.deferLater(self.reactor, self.retry_delay, lambda: None)
            else:
                logme = True
                if updates:
                    offset = max(update['update_id'] for update in updates) + 1
                    for update in updates:
                        self.process_update(update)


class TelegramBot(service.BuildbotService):
    name = "TelegramBot"

    in_test_harness = False

    compare_attrs = ["bot_token", "chat_ids", "authz",
                     "tags", "notify_events",
                     "showBlameList", "useRevisions",
                     "certificate", "usePolling",
                     "pollTimeout", "retryDelay"]
    secrets = ["bot_token"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.www = get_plugins('www', None, load_now=True)
        self.bot = None

    def _get_http(self, bot_token):
        base_url = "https://api.telegram.org/bot" + bot_token
        return httpclientservice.HTTPClientService.getService(
            self.master, base_url)

    def checkConfig(self, bot_token, chat_ids=None, authz=None,
                    bot_username=None, tags=None, notify_events=None,
                    showBlameList=True, useRevisions=False,
                    certificate=None, usePolling=False,
                    pollTimeout=120, retryDelay=30
                   ):
        super().checkConfig(self.name)

        if authz is not None:
            for acl in authz.values():
                if not isinstance(acl, (list, tuple, bool)):
                    config.error("authz values must be bool or a list of user ids")

        if isinstance(certificate, io.TextIOBase):
            config.error("certificate file must be open in binary mode")

    @defer.inlineCallbacks
    def reconfigService(self, bot_token, chat_ids=None, authz=None,
                        bot_username=None, tags=None, notify_events=None,
                        showBlameList=True, useRevisions=False,
                        certificate=None, usePolling=False,
                        pollTimeout=120, retryDelay=30
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
        self.usePolling = usePolling
        self.pollTimeout = pollTimeout
        self.retryDelay = retryDelay

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

        if usePolling:
            self.bot = TelegramPollingBot(bot_token, http, chat_ids, authz,
                                          tags=tags, notify_events=notify_events,
                                          useRevisions=useRevisions,
                                          showBlameList=showBlameList,
                                          poll_timeout=self.pollTimeout,
                                          retry_delay=self.retryDelay)
        else:
            self.bot = TelegramBotResource(bot_token, http, chat_ids, authz,
                                           tags=tags, notify_events=notify_events,
                                           useRevisions=useRevisions,
                                           showBlameList=showBlameList,
                                           retry_delay=self.retryDelay)
        if bot_username is not None:
            self.bot.nickname = bot_username
        else:
            yield self.bot.set_nickname()
            if self.bot.nickname is None:
                raise RuntimeError("No bot username specified and I cannot get it from Telegram")

        self.bot.setServiceParent(self)

        if not usePolling:
            bot_path = 'bot' + bot_token
            root.putChild(unicode2bytes(bot_path), self.bot)
            url = bytes2unicode(self.master.config.buildbotURL)
            if not url.endswith('/'): url += '/'
            self.bot.set_webhook(url + bot_path, certificate)
