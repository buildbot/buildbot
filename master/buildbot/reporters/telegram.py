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
from twisted.internet import reactor

from buildbot import config
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
from buildbot.reporters.words import WebhookResource
from buildbot.schedulers.forcesched import CollectedValidationError
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.util import Notifier
from buildbot.util import asyncSleep
from buildbot.util import bytes2unicode
from buildbot.util import epoch2datetime
from buildbot.util import httpclientservice
from buildbot.util import service
from buildbot.util import unicode2bytes


class TelegramChannel(Channel):

    def __init__(self, bot, channel):
        assert isinstance(channel, dict), "channel must be a dict provided by Telegram API"
        super().__init__(bot, channel['id'])
        self.chat_info = channel

    @defer.inlineCallbacks
    def list_notified_events(self):
        if self.notify_events:
            notified_events = "\n".join(sorted(f"🔔 **{n}**" for n in self.notify_events))
            yield self.send(f"The following events are being notified:\n{notified_events}")
        else:
            yield self.send("🔕 No events are being notified.")


def collect_fields(fields):
    for field in fields:
        if field['fullName']:
            yield field
        if 'fields' in field:
            yield from collect_fields(field['fields'])


class TelegramContact(Contact):

    def __init__(self, user, channel=None):
        assert isinstance(user, dict), "user must be a dict provided by Telegram API"
        self.user_info = user
        super().__init__(user['id'], channel)
        self.template = None

    @property
    def chat_id(self):
        return self.channel.id

    @property
    def user_full_name(self):
        fullname = " ".join((self.user_info['first_name'],
                             self.user_info.get('last_name', ''))).strip()
        return fullname

    @property
    def user_name(self):
        return self.user_info['first_name']

    def describeUser(self):
        user = self.user_full_name
        try:
            user += f" (@{self.user_info['username']})"
        except KeyError:
            pass

        if not self.is_private_chat:
            chat_title = self.channel.chat_info.get('title')
            if chat_title:
                user += f" on '{chat_title}'"

        return user

    ACCESS_DENIED_MESSAGES = [
        "🧙‍♂️ You shall not pass! 👹",
        "😨 Oh NO! You are simply not allowed to to this! 😢",
        "⛔ You cannot do this. Better go outside and relax... 🌳",
        "⛔ ACCESS DENIED! This incident has ben reported to NSA, KGB, and George Soros! 🕵",
        "🚫 Unauthorized access detected! Your device will explode in 3... 2... 1... 💣",
        "☢ Radiation level too high! Continuation of the procedure forbidden! 🛑",
    ]

    def access_denied(self, *args, tmessage, **kwargs):
        self.send(
            random.choice(self.ACCESS_DENIED_MESSAGES), reply_to_message_id=tmessage['message_id'])

    def query_button(self, caption, payload):
        if isinstance(payload, str) and len(payload) < 64:
            return {'text': caption, 'callback_data': payload}
        key = hash(repr(payload))
        while True:
            cached = self.bot.query_cache.get(key)
            if cached is None:
                self.bot.query_cache[key] = payload
                break
            if cached == payload:
                break
            key += 1
        return {'text': caption, 'callback_data': key}

    @defer.inlineCallbacks
    def command_START(self, args, **kwargs):
        self.bot.post('/setChatMenuButton', json={'chat_id': self.channel.id,
                                                  'menu_button': {'type': 'commands'}})
        yield self.command_HELLO(args)
        reactor.callLater(0.2, self.command_HELP, '')

    def command_NAY(self, args, tmessage, **kwargs):
        """forget the current command"""
        replied_message = tmessage.get('reply_to_message')
        if replied_message:
            if 'reply_markup' in replied_message:
                self.bot.edit_keyboard(self.channel.id,
                                       replied_message['message_id'])
        if self.is_private_chat:
            self.send("Never mind...")
        else:
            self.send(f"Never mind, {self.user_name}...")
    command_NAY.usage = "nay - never mind the command we are currently discussing"

    @classmethod
    def get_commands(cls):
        commands = cls.build_commands()
        response = []
        for command in commands:
            if command == 'start':
                continue
            meth = getattr(cls, 'command_' + command.upper())
            doc = getattr(meth, '__doc__', None)
            if not doc:
                doc = command
            response.append((command, doc))
        return response

    @classmethod
    def describe_commands(cls):
        return [f"{command} - {doc}" for command, doc in cls.get_commands()]

    @Contact.overrideCommand
    def command_COMMANDS(self, args, **kwargs):
        if args.lower() == 'botfather':
            response = self.describe_commands()
            if response:
                self.send('\n'.join(response))
        else:
            return super().command_COMMANDS(args)
        return None

    @defer.inlineCallbacks
    def command_GETID(self, args, **kwargs):
        """get user and chat ID"""
        if self.is_private_chat:
            self.send(f"Your ID is `{self.user_id}`.")
        else:
            yield self.send(f"{self.user_name}, your ID is `{self.user_id}`.")
            self.send(f'This {self.channel.chat_info.get("type", "group")} ID is `{self.chat_id}`.')
    command_GETID.usage = "getid - get user and chat ID that can be put in the master " \
                          "configuration file"

    @defer.inlineCallbacks
    @Contact.overrideCommand
    def command_LIST(self, args, **kwargs):
        args = self.splitArgs(args)
        if not args:
            keyboard = [
                [self.query_button("👷️ Builders", '/list builders'),
                 self.query_button("👷️ (including old ones)", '/list all builders')],
                [self.query_button("⚙ Workers", '/list workers'),
                 self.query_button("⚙ (including old ones)", '/list all workers')],
                [self.query_button("📄 Changes (last 10)", '/list changes')],
            ]
            self.send("What do you want to list?",
                      reply_markup={'inline_keyboard': keyboard})
            return

        all = False
        num = 10
        try:
            num = int(args[0])
            del args[0]
        except ValueError:
            if args[0] == 'all':
                all = True
                del args[0]
        except IndexError:
            pass

        if not args:
            raise UsageError("Try '" + self.bot.commandPrefix +
                             "list [all|N] builders|workers|changes'.")

        if args[0] == 'builders':
            bdicts = yield self.bot.getAllBuilders()
            online_builderids = yield self.bot.getOnlineBuilders()

            response = ["I found the following **builders**:"]
            for bdict in bdicts:
                if bdict['builderid'] in online_builderids:
                    response.append(f"`{bdict['name']}`")
                elif all:
                    response.append(f"`{bdict['name']}` ❌")
            self.send('\n'.join(response))

        elif args[0] == 'workers':
            workers = yield self.master.data.get(('workers',))

            response = ["I found the following **workers**:"]
            for worker in workers:
                if worker['configured_on']:
                    response.append(f"`{worker['name']}`")
                    if not worker['connected_to']:
                        response[-1] += " ⚠️"
                elif all:
                    response.append(f"`{worker['name']}` ❌")
            self.send('\n'.join(response))

        elif args[0] == 'changes':

            wait_message = yield self.send("⏳ Getting your changes...")

            if all:
                changes = yield self.master.data.get(('changes',))
                self.bot.delete_message(self.channel.id, wait_message['message_id'])
                num = len(changes)
                if num > 50:
                    keyboard = [
                        [self.query_button("‼ Yes, flood me with all of them!",
                                           f'/list {num} changes')],
                        [self.query_button("✅ No, just show last 50", '/list 50 changes')]
                    ]
                    self.send(f"I found {num} changes. Do you really want me to list them all?",
                              reply_markup={'inline_keyboard': keyboard})
                    return

            else:
                changes = yield self.master.data.get(('changes',), order=['-changeid'], limit=num)
                self.bot.delete_message(self.channel.id, wait_message['message_id'])

            response = ["I found the following recent **changes**:\n"]

            for change in reversed(changes):
                change['comment'] = change['comments'].split('\n')[0]
                change['date'] = epoch2datetime(change['when_timestamp']).strftime('%Y-%m-%d %H:%M')
                response.append(
                    f"[{change['comment']}]({change['revlink']})\n"
                    f"_Author_: {change['author']}\n"
                    f"_Date_: {change['date']}\n"
                    f"_Repository_: {change['repository']}\n"
                    f"_Branch_: {change['branch']}\n"
                    f"_Revision_: {change['revision']}\n")
            self.send('\n'.join(response))

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
                    [self.query_button("🔎 " + b, f'/watch {b}')]
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
                self.bot.delete_message(self.chat_id, tquery['message']['message_id'])

            super().command_NOTIFY(args)

            if want_list or not tquery:
                return

        keyboard = [
            [
                self.query_button(
                    f"{e.capitalize()} {'🔔' if e in self.channel.notify_events else '🔕'}",
                    f"/notify {'off' if e in self.channel.notify_events else 'on'}-quiet {e}")
                for e in evs
            ]
            for evs in (('started', 'finished'), ('success', 'failure'), ('warnings', 'exception'),
                        ('problem', 'recovery'), ('worse', 'better'), ('cancelled', 'worker'))
        ] + [[self.query_button("Hide...", '/notify list')]]

        if tquery:
            self.bot.edit_keyboard(self.chat_id, tquery['message']['message_id'], keyboard)
        else:
            self.send("Here are available notifications and their current state. "
                      "Click to turn them on/off.",
                      reply_markup={'inline_keyboard': keyboard})

    def ask_for_reply(self, prompt, greeting='Ok'):
        kwargs = {}
        if not self.is_private_chat:
            username = self.user_info.get('username', '')
            if username:
                if greeting:
                    prompt = f"{greeting} @{username}, now {prompt}..."
                else:
                    prompt = f"@{username}, now {prompt}..."
                kwargs['reply_markup'] = {
                    'force_reply': True,
                    'selective': True
                }
            else:
                if greeting:
                    prompt = f"{greeting}, now reply to this message and {prompt}..."
                else:
                    prompt = f"Reply to this message and {prompt}..."
        else:
            if greeting:
                prompt = f"{greeting}, now {prompt}..."
            else:
                prompt = prompt[0].upper() + prompt[1:] + "..."
            # Telegram seems to have a bug, which causes reply request to pop sometimes again.
            # So we do not force reply to avoid it...
            # kwargs['reply_markup'] = {
            #     'force_reply': True
            # }
        self.send(prompt, **kwargs)

    @defer.inlineCallbacks
    @Contact.overrideCommand
    def command_STOP(self, args, **kwargs):
        argv = self.splitArgs(args)
        if len(argv) >= 3 or \
                argv and argv[0] != 'build':
            super().command_STOP(args)
            return
        argv = argv[1:]
        if not argv:
            builders = yield self.get_running_builders()
            if builders:
                keyboard = [
                    [self.query_button("🚫 " + b, f'/stop build {b}')]
                    for b in builders
                ]
                self.send("Select builder to stop...",
                          reply_markup={'inline_keyboard': keyboard})
        else:  # len(argv) == 1
            self.template = '/stop ' + args + ' {}'
            self.ask_for_reply(f"give me the reason to stop build on `{argv[0]}`")

    @Contact.overrideCommand
    def command_SHUTDOWN(self, args, **kwargs):
        if args:
            return super().command_SHUTDOWN(args)
        if self.master.botmaster.shuttingDown:
            keyboard = [[
                 self.query_button("🔙 Stop Shutdown", '/shutdown stop'),
                 self.query_button("‼️ Shutdown Now", '/shutdown now')
            ]]
            text = "Buildbot is currently shutting down.\n\n"
        else:
            keyboard = [[
                 self.query_button("↘️ Begin Shutdown", '/shutdown start'),
                 self.query_button("‼️ Shutdown Now", '/shutdown now')
            ]]
            text = ""
        self.send(text + "What do you want to do?",
                  reply_markup={'inline_keyboard': keyboard})
        return None

    @defer.inlineCallbacks
    def command_FORCE(self, args, tquery=None, partial=None, **kwargs):
        """force a build"""

        try:
            forceschedulers = yield self.master.data.get(('forceschedulers',))
        except AttributeError:
            forceschedulers = None
        else:
            forceschedulers = dict((s['name'], s) for s in forceschedulers)

        if not forceschedulers:
            raise UsageError("no force schedulers configured for use by /force")

        argv = self.splitArgs(args)

        try:
            sched = argv[0]
        except IndexError:
            if len(forceschedulers) == 1:
                sched = next(iter(forceschedulers))
            else:
                keyboard = [
                    [self.query_button(s['label'], f"/force {s['name']}")]
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
            else:
                raise UsageError("Try '/force' and follow the instructions"
                                 f" (no force scheduler {sched})")
        scheduler = forceschedulers[sched]

        try:
            task = argv.pop(0)
        except IndexError:
            task = 'config'

        if tquery and task != 'config':
            self.bot.edit_keyboard(self.chat_id, tquery['message']['message_id'])

        if not argv:
            keyboard = [
                [self.query_button(b, f'/force {sched} {task} {b}')]
                for b in scheduler['builder_names']
            ]
            self.send("Which builder do you want to start?",
                      reply_markup={'inline_keyboard': keyboard})
            return

        if task == 'ask':
            try:
                what = argv.pop(0)
            except IndexError as e:
                raise UsageError("Try '/force' and follow the instructions") from e
        else:
            what = None  # silence PyCharm warnings

        bldr = argv.pop(0)
        if bldr not in scheduler['builder_names']:
            raise UsageError("Try '/force' and follow the instructions "
                             f"(`{bldr}` not configured for _{scheduler['label']}_ scheduler)")

        try:
            params = dict(arg.split('=', 1) for arg in argv)
        except ValueError as e:
            raise UsageError(f"Try '/force' and follow the instructions ({e})") from e

        all_fields = list(collect_fields(scheduler['all_fields']))
        required_params = [f['fullName'] for f in all_fields
                           if f['required'] and f['fullName'] not in ('username', 'owner')]
        missing_params = [p for p in required_params if p not in params]

        if task == 'build':
            # TODO This should probably be moved to the upper class,
            # however, it will change the force command totally

            try:
                if missing_params:
                    # raise UsageError
                    task = 'config'
                else:
                    params.update(dict(
                        (f['fullName'], f['default']) for f in all_fields
                        if f['type'] == 'fixed' and f['fullName'] not in ('username', 'owner')
                    ))

                    builder = yield self.bot.getBuilder(buildername=bldr)
                    for scheduler in self.master.allSchedulers():
                        if scheduler.name == sched and isinstance(scheduler, ForceScheduler):
                            break
                    else:
                        raise ValueError(f"There is no force scheduler '{sched}'")
                    try:
                        yield scheduler.force(builderid=builder['builderid'],
                                              owner=self.describeUser(),
                                              **params)
                    except CollectedValidationError as e:
                        raise ValueError(e.errors) from e
                    self.send("Force build successfully requested.")
                    return

            except (IndexError, ValueError) as e:
                raise UsageError(f"Try '/force' and follow the instructions ({e})") from e

        if task == 'config':

            msg = f"{self.user_full_name}, you are about to start a new build on `{bldr}`!"

            keyboard = []
            args = ' '.join(shlex.quote(f"{p[0]}={p[1]}") for p in params.items())

            fields = [f for f in all_fields if f['type'] != 'fixed'
                      and f['fullName'] not in ('username', 'owner')]

            if fields:
                msg += "\n\nThe current build parameters are:"
                for field in fields:
                    if field['type'] == 'nested':
                        msg += f"\n{field['label']}"
                    else:
                        field_name = field['fullName']
                        value = params.get(field_name, field['default'])
                        if isinstance(value, str):
                            value = value.strip()
                        msg += f"\n    {field['label']} `{value}`"
                        if value:
                            key = "Change "
                        else:
                            key = "Set "
                        key += field_name.replace('_', ' ').title()
                        if field_name in missing_params:
                            key = "⚠️ " + key
                            msg += " ⚠️"
                        keyboard.append(
                            [self.query_button(key,
                                f'/force {sched} ask {field_name} {bldr} {args}')]
                        )

            msg += "\n\nWhat do you want to do?"
            if missing_params:
                msg += " You must set values for all parameters marked with ⚠️"

            if not missing_params:
                keyboard.append(
                    [self.query_button("🚀 Start Build", f'/force {sched} build {bldr} {args}')],
                )

            self.send(msg, reply_markup={'inline_keyboard': keyboard})

        elif task == 'ask':
            prompt = "enter the new value for the " + what.replace('_', ' ').lower()
            args = ' '.join(shlex.quote(f"{p[0]}={p[1]}") for p in params.items()
                            if p[0] != what)
            self.template = f'/force {sched} config {bldr} {args} {what}={{}}'
            self.ask_for_reply(prompt, '')

        else:
            raise UsageError("Try '/force' and follow the instructions")

    command_FORCE.usage = "force - Force a build"


class TelegramStatusBot(StatusBot):

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

    @defer.inlineCallbacks
    def startService(self):
        yield super().startService()
        for c in self.chat_ids:
            channel = self.getChannel(c)
            channel.add_notification_events(self.notify_events)
        yield self.loadState()
        commands = [{'command': command, 'description': doc}
                    for command, doc in TelegramContact.get_commands()]
        self.post('/setMyCommands', json={'commands': commands})

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

    def getContact(self, user, channel):
        """ get a Contact instance for ``user`` on ``channel`` """
        assert isinstance(user, dict), "user must be a dict provided by Telegram API"
        assert isinstance(channel, dict), "channel must be a dict provided by Telegram API"

        uid = user['id']
        cid = channel['id']
        try:
            contact = self.contacts[(cid, uid)]
        except KeyError:
            valid = self.isValidUser(uid)
            contact = self.contactClass(user=user,
                                        channel=self.getChannel(channel, valid))
            if valid:
                self.contacts[(cid, uid)] = contact
        else:
            if isinstance(user, dict):
                contact.user_info.update(user)
            if isinstance(channel, dict):
                contact.channel.chat_info.update(channel)
        return contact

    def getChannel(self, channel, valid=True):
        if not isinstance(channel, dict):
            channel = {'id': channel}
        cid = channel['id']
        try:
            return self.channels[cid]
        except KeyError:
            new_channel = self.channelClass(self, channel)
            if valid:
                self.channels[cid] = new_channel
                new_channel.setServiceParent(self)
            return new_channel

    @defer.inlineCallbacks
    def process_update(self, update):
        data = {}

        message = update.get('message')
        if message is None:
            query = update.get('callback_query')
            if query is None:
                self.log('No message in Telegram update object')
                return 'no message'
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

        chat = message['chat']

        user = message.get('from')
        if user is None:
            self.log('No user in incoming message')
            return 'no user'

        text = message.get('text')
        if not text:
            return 'no text in the message'

        contact = self.getContact(user=user, channel=chat)
        data['tmessage'] = message
        template, contact.template = contact.template, None
        if text.startswith(self.commandPrefix):
            result = yield contact.handleMessage(text, **data)
        else:
            if template:
                text = template.format(shlex.quote(text))
            result = yield contact.handleMessage(text, **data)
        return result

    @defer.inlineCallbacks
    def post(self, path, **kwargs):
        logme = True
        while True:
            try:
                res = yield self.http_client.post(path, **kwargs)
            except AssertionError as err:
                # just for tests
                raise err
            except Exception as err:
                msg = f"ERROR: problem sending Telegram request {path} (will try again): {err}"
                if logme:
                    self.log(msg)
                    logme = False
                yield asyncSleep(self.retry_delay)
            else:
                ans = yield res.json()
                if not ans.get('ok'):
                    self.log(f"ERROR: cannot send Telegram request {path}: "
                             f"[{res.code}] {ans.get('description')}")
                    return None
                return ans.get('result', True)

    @defer.inlineCallbacks
    def set_nickname(self):
        res = yield self.post('/getMe')
        if res:
            self.nickname = res.get('username')

    @defer.inlineCallbacks
    def answer_query(self, query_id, notify=None):
        params = {"callback_query_id": query_id}
        if notify is not None:
            params.update({"text": notify})
        return (yield self.post('/answerCallbackQuery', json=params))

    @defer.inlineCallbacks
    def send_message(self, chat, message, parse_mode='Markdown',
                     reply_to_message_id=None, reply_markup=None,
                     **kwargs):
        result = None

        message = message.strip()
        while message:
            params = {"chat_id": chat}
            if parse_mode is not None:
                params['parse_mode'] = parse_mode
            if reply_to_message_id is not None:
                params['reply_to_message_id'] = reply_to_message_id
                reply_to_message_id = None  # we only mark first message as a reply

            if len(message) <= 4096:
                params['text'], message = message, None
            else:
                n = message[:4096].rfind('\n')
                n = n + 1 if n != -1 else 4096
                params['text'], message = message[:n].rstrip(), message[n:].lstrip()

            if not message and reply_markup is not None:
                params['reply_markup'] = reply_markup

            params.update(kwargs)

            result = yield self.post('/sendMessage', json=params)

        return result

    @defer.inlineCallbacks
    def edit_message(self, chat, msg, message, parse_mode='Markdown', **kwargs):
        params = {"chat_id": chat, "message_id": msg, "text": message}
        if parse_mode is not None:
            params['parse_mode'] = parse_mode
        params.update(kwargs)
        return (yield self.post('/editMessageText', json=params))

    @defer.inlineCallbacks
    def edit_keyboard(self, chat, msg, keyboard=None):
        params = {"chat_id": chat, "message_id": msg}
        if keyboard is not None:
            params['reply_markup'] = {'inline_keyboard': keyboard}
        return (yield self.post('/editMessageReplyMarkup', json=params))

    @defer.inlineCallbacks
    def delete_message(self, chat, msg):
        params = {"chat_id": chat, "message_id": msg}
        return (yield self.post('/deleteMessage', json=params))

    @defer.inlineCallbacks
    def send_sticker(self, chat, sticker, **kwargs):
        params = {"chat_id": chat, "sticker": sticker}
        params.update(kwargs)
        return (yield self.post('/sendSticker', json=params))


class TelegramWebhookBot(TelegramStatusBot):
    name = "TelegramWebhookBot"

    def __init__(self, token, *args, certificate=None, **kwargs):
        TelegramStatusBot.__init__(self, token, *args, **kwargs)
        self._certificate = certificate
        self.webhook = WebhookResource('telegram' + token)
        self.webhook.setServiceParent(self)

    @defer.inlineCallbacks
    def startService(self):
        yield super().startService()
        url = bytes2unicode(self.master.config.buildbotURL)
        if not url.endswith('/'):
            url += '/'
        yield self.set_webhook(url + self.webhook.path, self._certificate)

    def process_webhook(self, request):
        update = self.get_update(request)
        return self.process_update(update)

    def get_update(self, request):
        content = request.content.read()
        content = bytes2unicode(content)
        content_type = request.getHeader(b'Content-Type')
        content_type = bytes2unicode(content_type)
        if content_type is not None and \
                content_type.startswith('application/json'):
            update = json.loads(content)
        else:
            raise ValueError(f'Unknown content type: {content_type}')
        return update

    @defer.inlineCallbacks
    def set_webhook(self, url, certificate=None):
        if not certificate:
            self.log(f"Setting up webhook to: {url}")
            yield self.post('/setWebhook', json={"url": url})
        else:
            self.log(f"Setting up webhook to: {url} (custom certificate)")
            certificate = io.BytesIO(unicode2bytes(certificate))
            yield self.post('/setWebhook', data={"url": url},
                            files={"certificate": certificate})


class TelegramPollingBot(TelegramStatusBot):
    name = "TelegramPollingBot"

    def __init__(self, *args, poll_timeout=120, **kwargs):
        super().__init__(*args, **kwargs)
        self._polling_finished_notifier = Notifier()
        self.poll_timeout = poll_timeout

    def startService(self):
        super().startService()
        self._polling_continue = True
        self.do_polling()

    @defer.inlineCallbacks
    def stopService(self):
        self._polling_continue = False
        yield self._polling_finished_notifier.wait()
        yield super().stopService()

    @defer.inlineCallbacks
    def do_polling(self):
        yield self.post('/deleteWebhook')
        offset = 0
        kwargs = {'json': {'timeout': self.poll_timeout}}
        logme = True
        while self._polling_continue:
            if offset:
                kwargs['json']['offset'] = offset
            try:
                res = yield self.http_client.post('/getUpdates',
                                                  timeout=self.poll_timeout + 2,
                                                  **kwargs)
                ans = yield res.json()
                if not ans.get('ok'):
                    raise ValueError(f"[{res.code}] {ans.get('description')}")
                updates = ans.get('result')
            except AssertionError as err:
                raise err
            except Exception as err:
                msg = f"ERROR: cannot send Telegram request /getUpdates (will try again): {err}"
                if logme:
                    self.log(msg)
                    logme = False
                yield asyncSleep(self.retry_delay)
            else:
                logme = True
                if updates:
                    offset = max(update['update_id'] for update in updates) + 1
                    for update in updates:
                        yield self.process_update(update)

        self._polling_finished_notifier.notify(None)


class TelegramBot(service.BuildbotService):
    name = "TelegramBot"

    in_test_harness = False

    compare_attrs = ["bot_token", "chat_ids", "authz",
                     "tags", "notify_events",
                     "showBlameList", "useRevisions",
                     "certificate", "useWebhook",
                     "pollTimeout", "retryDelay"]
    secrets = ["bot_token"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = None

    def _get_http(self, bot_token):
        base_url = "https://api.telegram.org/bot" + bot_token
        return httpclientservice.HTTPClientService.getService(
            self.master, base_url)

    def checkConfig(self, bot_token, chat_ids=None, authz=None,
                    bot_username=None, tags=None, notify_events=None,
                    showBlameList=True, useRevisions=False,
                    useWebhook=False, certificate=None,
                    pollTimeout=120, retryDelay=30):
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
                        useWebhook=False, certificate=None,
                        pollTimeout=120, retryDelay=30):
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
        self.useWebhook = useWebhook
        self.certificate = certificate
        self.pollTimeout = pollTimeout
        self.retryDelay = retryDelay

        # This function is only called in case of reconfig with changes
        # We don't try to be smart here. Just restart the bot if config has
        # changed.

        http = yield self._get_http(bot_token)

        if self.bot is not None:
            self.removeService(self.bot)

        if not useWebhook:
            self.bot = TelegramPollingBot(bot_token, http, chat_ids, authz,
                                          tags=tags, notify_events=notify_events,
                                          useRevisions=useRevisions,
                                          showBlameList=showBlameList,
                                          poll_timeout=self.pollTimeout,
                                          retry_delay=self.retryDelay)
        else:
            self.bot = TelegramWebhookBot(bot_token, http, chat_ids, authz,
                                          tags=tags, notify_events=notify_events,
                                          useRevisions=useRevisions,
                                          showBlameList=showBlameList,
                                          retry_delay=self.retryDelay,
                                          certificate=self.certificate)
        if bot_username is not None:
            self.bot.nickname = bot_username
        else:
            yield self.bot.set_nickname()
            if self.bot.nickname is None:
                raise RuntimeError("No bot username specified and I cannot get it from Telegram")

        yield self.bot.setServiceParent(self)
