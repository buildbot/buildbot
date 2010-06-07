class State(object):
    """
    A simple class you can use to keep track of state throughout
    a test.  Just assign whatever you want to its attributes.  Its
    constructor provides a shortcut to setting initial values for
    attributes
    """
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
