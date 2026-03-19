class _Singleton(type):
    """
    A metaclass that creates a Singleton base class when called.
    The instance is identified by the super class and the arguments passed to it.
    @reference: https://stackoverflow.com/questions/6760685/what-is-the-best-way-of-implementing-singleton-in-python
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        args_hash = hash(args + tuple(sorted(kwargs.items())))
        if cls not in cls._instances:
            cls._instances[cls] = {}
        if args_hash not in cls._instances[cls]:
            cls._instances[cls][args_hash] = super(_Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls][args_hash]


class Singleton(_Singleton('SingletonMeta', (object,), {})):
    pass
