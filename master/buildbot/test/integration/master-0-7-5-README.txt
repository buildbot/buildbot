-- 0.7.5 historical master tarball --

This tarball exists to allow testing upgrades of old versions.  It was created
by running the master against the included master.cfg using a normal
buildbot.tac.  The slave was connected, and a few changes sent, including one
with some funny characters in it:

$ snowman=`python -c 'print u"\N{SNOWMAN}".encode("utf-8")'`
$ black_star=`python -c 'print u"\N{BLACK STAR}".encode("utf-8")'`
$ comet=`python -c 'print u"\N{COMET}".encode("utf-8")'`
$ buildbot sendchange --master=localhost:9989 -u \
        "the snowman <$snowman@norpole.net>" \
        --revision="${black_star}-devel" -b "$comet" \
        --comments "shooting star or $comet?" \
        "$black_star/funny_chars/in/a/path" "normal/path"
$ buildbot sendchange --master=localhost:9989
        -u "dustin <dustin@v.igoro.us>" --revision="1234"
        --comments "on-branch change" boring/path

0.7.5 did not support change properties from sendchange.

Note that the master.cfg also puts a funny character in stdout (in UTF-8).
