"""Reading the action inputs, and talking back to the workflow."""

import os
import uuid

# Exit status when the request is wrong. A suite that ran and failed
# returns its own.
FAILURE = 2


def log(message):
    print(message, flush=True)


def warn(message):
    log("::warning::" + message)


def fail(message):
    log("::error::" + message)
    raise SystemExit(FAILURE)


def mask(secret):
    """Hide a value from everything the workflow logs after this."""
    if secret:
        log("::add-mask::" + secret)


def get(name, default="", required=False):
    """An input, stripped. Blank counts as unset."""
    value = os.environ.get("INPUT_" + name.upper(), "").strip()
    if value:
        return value
    if required:
        fail(name + " is required")
    return default


def get_int(name, default):
    value = get(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        fail(f"{name} is not a number: {value}")


def lines(name):
    """The non-empty lines of a multi-line input, stripped."""
    return [line.strip() for line in get(name).splitlines() if line.strip()]


def set_output(name, value):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    value = str(value)
    with open(path, "a", encoding="utf-8") as handle:
        if "\n" in value:
            # Newlines need the delimiter form, and the delimiter must
            # not occur in the value.
            marker = "delimiter_" + uuid.uuid4().hex
            handle.write(f"{name}<<{marker}\n{value}\n{marker}\n")
        else:
            handle.write(f"{name}={value}\n")
