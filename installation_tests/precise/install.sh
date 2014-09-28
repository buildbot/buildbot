mkdir /buildbot
cd /buildbot
unzip /tmp/master.zip
cd buildbot-pkg_fixes
export BUILDBOT_VERSION=0.9.0-pre
pip install mock wheel

for i in ./pkg ./master 
do
    ( cd $i;  python setup.py install )
done
cd pkg
trial test*.py
