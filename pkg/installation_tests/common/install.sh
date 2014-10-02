cd /buildbot

unzip master.zip

cd buildbot-master

# as we are running from a git archive of buildbot, we dont have the tags, or VERSION files.
# we just use a fake version number
export BUILDBOT_VERSION=0.9.0-pre

# mock and wheel are build deps for those tests
pip install mock wheel

for i in ./pkg ./master ./slave
do
    ( cd $i;  python setup.py install )
done
cd pkg
trial test*.py
