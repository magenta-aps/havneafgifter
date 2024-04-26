# Copied from core python because its containing module `distutils` is deprecated.
from django.shortcuts import render


def strtobool(val):
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return 1
    elif val in ("n", "no", "f", "false", "off", "0"):
        return 0
    else:
        raise ValueError("invalid truth value %r" % (val,))


def template_failure(request, exception=None, status=403, **kwargs):
    print(exception)
    """ Renders a simple template with an error message. """
    return render(request, 'djangosaml2/login_error.html', {'exception': exception}, status=status)
