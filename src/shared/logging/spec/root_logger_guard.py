import logging
import warnings

_originals = {}


def install():
    root = logging.getLogger()
    _originals["addHandler"] = root.addHandler
    _originals["setLevel"] = root.setLevel

    def guarded_add_handler(handler):
        warnings.warn("Root logger mutation blocked: addHandler called after spec config", stacklevel=2)
        _originals["addHandler"](handler)

    def guarded_set_level(level):
        warnings.warn("Root logger mutation blocked: setLevel called after spec config", stacklevel=2)
        _originals["setLevel"](level)

    root.addHandler = guarded_add_handler
    root.setLevel = guarded_set_level


def uninstall():
    if _originals:
        root = logging.getLogger()
        root.addHandler = _originals.pop("addHandler", root.addHandler)
        root.setLevel = _originals.pop("setLevel", root.setLevel)
