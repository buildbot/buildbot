# Execute 'vagrant up' and 'vagrant ssh'.
# Requires VirtualBox is installed.

# Configure FORK and BRANCH to pull from.
FORK = 'buildbot'
BRANCH = 'master'

# Enable developer tests here
TEST_MIGRATION = 'true'



Vagrant.configure(2) do |config|
  config.vm.define "buildbot" do |buildbot|
    buildbot.vm.box = "centos/7"
    buildbot.vm.box_check_update = true
    buildbot.vm.synced_folder '.', '/vagrant', disabled: true
    buildbot.vm.provider "virtualbox" do |vb|
      vb.gui = false
      #vb.memory = "2048"
      #vb.cpus = "8"
    end
    buildbot.vm.provision "shell", inline: <<-SHELL
      set -o errexit
      set -o nounset

      echo "installing deps:"
      yum -y group install development
      yum -y install python-devel epel-release openssl-devel libffi-devel
      yum -y install python-pip
      pip install --upgrade pip virtualenv setuptools
    SHELL
    buildbot.vm.provision "shell", privileged: false, args: [FORK, BRANCH], inline: <<-SHELL
      set -o errexit
      DATE=$(date +%s)

      echo "installing buildbot:"
      rm -rf /home/vagrant/buildbot
      git clone -b $2 https://github.com/$1/buildbot.git
      rm -rf /home/vagrant/.bb_venv
      virtualenv /home/vagrant/.bb_venv
      source /home/vagrant/.bb_venv/bin/activate
      cd /home/vagrant/buildbot
      make prebuilt_frontend
      cd /home/vagrant/buildbot/master
      python setup.py build
      python setup.py install
      cd /home/vagrant/buildbot/worker
      python setup.py build
      python setup.py install

      echo "configuring buildbot:"
      buildbot create-master /tmp/bb-$DATE
      mv -fv /tmp/bb-$DATE/master.cfg.sample /tmp/bb-$DATE/master.cfg
      echo "c['buildbotNetUsageData'] = None" | tee -a /tmp/bb-$DATE/master.cfg
      nl /tmp/bb-$DATE/master.cfg

      echo "upgrading database:"
      buildbot upgrade-master /tmp/bb-$DATE

      echo "up and down buildbot:"
      buildbot start /tmp/bb-$DATE
      curl localhost:8010
      nl /tmp/bb-$DATE/twistd.log
      buildbot-worker create-worker /tmp/bb-worker-$DATE localhost example-worker pass
      buildbot-worker start /tmp/bb-worker-$DATE
      nl /tmp/bb-worker-$DATE/twistd.log
      buildbot-worker stop /tmp/bb-worker-$DATE
      nl /tmp/bb-worker-$DATE/twistd.log
      buildbot stop /tmp/bb-$DATE
      nl /tmp/bb-$DATE/twistd.log

      echo "running tests:"
      pip install mock treq ramlfications lz4 moto txrequests
      cd /home/vagrant/buildbot
      trial buildbot.test

      echo "source ~/.bb_venv/bin/activate" | tee -a ~/.bashrc
    SHELL
    if TEST_MIGRATION == 'true'
      buildbot.vm.provision "shell", privileged: false, inline: <<-SHELL
        set -o errexit
        DATE=$(date +%s)

        echo "test migration:"
        buildbot create-master /tmp/bb-mig-$DATE
        mv -fv /tmp/bb-mig-$DATE/master.cfg.sample /tmp/bb-mig-$DATE/master.cfg
        echo "c['buildbotNetUsageData'] = None" | tee -a /tmp/bb-mig-$DATE/master.cfg
        nl /tmp/bb-mig-$DATE/master.cfg
        buildbot start /tmp/bb-mig-$DATE
        nl /tmp/bb-mig-$DATE/twistd.log
        buildbot stop /tmp/bb-mig-$DATE
        nl /tmp/bb-mig-$DATE/twistd.log
        sqlite3 -line /tmp/bb-mig-$DATE/state.sqlite ".schema change_properties"
        cd /home/vagrant/buildbot/master
        git remote add nando https://github.com/nand0p/buildbot.git
        git fetch --all
        git checkout 3197_change_properties_to_text
        python setup.py build
        python setup.py install
        buildbot upgrade-master /tmp/bb-mig-$DATE
        sqlite3 -line /tmp/bb-mig-$DATE/state.sqlite ".schema change_properties"
      SHELL
    end
    buildbot.vm.provision "shell", privileged: false, inline: <<-SHELL
        echo "all g00d."
    SHELL
  end
end
