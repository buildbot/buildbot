import os

from twisted.python.procutils import which

def getCommand(name):
    possibles = which(name)
    if not possibles:
        raise RuntimeError("Couldn't find executable for '%s'" % name)
    return possibles[0]

def rmdirRecursive(dir):
    """This is a replacement for shutil.rmtree that works better under
    windows. Thanks to Bear at the OSAF for the code."""
    if not os.path.exists(dir):
        return

    if os.path.islink(dir):
        os.remove(dir)
        return

    # Verify the directory is read/write/execute for the current user
    os.chmod(dir, 0700)

    for name in os.listdir(dir):
        full_name = os.path.join(dir, name)
        # on Windows, if we don't have write permission we can't remove
        # the file/directory either, so turn that on
        if os.name == 'nt':
            if not os.access(full_name, os.W_OK):
                # I think this is now redundant, but I don't have an NT
                # machine to test on, so I'm going to leave it in place
                # -warner
                os.chmod(full_name, 0600)

        if os.path.isdir(full_name):
            rmdirRecursive(full_name)
        else:
            if os.path.isfile(full_name):
                os.chmod(full_name, 0700)
            os.remove(full_name)
    os.rmdir(dir)

