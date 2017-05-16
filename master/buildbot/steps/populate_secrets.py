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
'''
# First we declare that the secrets are stored in a directory of the filesystem
# each file contain one secret identified by the filename
c['secretsManagers'] = [util.SecretInFile(directory="/path/toSecretsFiles"]

# then in a buildfactory:

f1.addStep(PopulateSecrets([
  #  populate a secret by putting the whole data in the file
  dict(secret_worker_path="~/.ssh/id_rsa", secret_keys="ssh_user1"),

  #  populate a secret by putting the secrets inside a template
  dict(secret_worker_path="~/.netrc", template="""
  machine ftp.mycompany.com
    login buildbot
    password {ftppassword}
    machine www.mycompany.com
      login buildbot
      password {webpassword}
  """, secret_keys=["ftppassword", "webpassword"])])

#  use a secret on a shell command via Interpolate
f1.addStep(ShellCommand(Interpolate("wget -u user -p %{secrets:userpassword}s %{prop:urltofetch}s")))

# Remove secrets remove all the secrets that was populated before
f1.addStep(RemoveSecrets())
'''

from __future__ import absolute_import
from __future__ import print_function

from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep


class PopulatedSecret():

    def __init__(self, path, secretkeys, template=None):
        self.path = path
        if not isinstance(self.path, str):
            raise ValueError("secret path %s is not a string" % keys)
        self.keys = keys
        if template is None:
            template = """ """
        self.template = template

    @defer.inlineCallbacks
    def completeTemplate(self, credsservice):
        secrets_details_dict = dict({})
        for secretkey in secretkeys:
            secret_detail = yield credsservice.get(self.secret_name)
            if secret_detail is None:
                raise KeyError("secret key %s is not found in any provider" % secretkey)
            secrets_details_dict.update({secret_detail.key: secret_detail.value})
        defer.returnValue(self.template.format(**secrets_details_dict))

    @defeer.inlineCallbacks
    def createFile(self, credsservice):
        if self.template:
            text = yield self.completeTemplate(credsservice)
        else:
            text = secret


class PopulateSecrets(BuildStep):
'''
    f1.addStep(PopulateSecrets([
  #  populate a secret by putting the whole data in the file
  dict(secret_worker_path="~/.ssh/id_rsa", secret_keys="ssh_user1"),

  #  populate a secret by putting the secrets inside a template
  dict(secret_worker_path="~/.netrc", template="""
  machine ftp.mycompany.com
    login buildbot
    password {ftppassword}
    machine www.mycompany.com
      login buildbot
      password {webpassword}
  """, secret_keys=["ftppassword", "webpassword"])])

'''
    def __init__(self, populated_secret_list):
        self.populated_secret_list = populated_secret_list

    def runPopulateSecrets(self):
        secretsSrv = self.build.master.namedServices.get("secrets")
        if not secretsSrv:
            error_message = "secrets service not started, need to configure" \
                            " SecretManager in c['services'] to use 'secrets'" \
                            "in Interpolate"
            raise KeyError(error_message)
        credsservice = self.build.master.namedServices['secrets']

        for secret in self.populated_secret_list:
            secret.createFile(credsservice)
        return SUCCESS

    def run(self):
        return self.runPopulateSecrets()
