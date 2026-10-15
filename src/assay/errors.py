"""Exception hierarchy.

Every failure a user can act on raises a subclass of AssayError. The message
says what failed and what to do next. The CLI prints it without a traceback
and exits with the subclass's code.
"""


class AssayError(Exception):
    exit_code = 1


class ConfigError(AssayError):
    """A profile, option or setting is missing or invalid."""

    exit_code = 3


class DataError(AssayError):
    """Benchmark data is missing, has changed or does not pair up."""

    exit_code = 4


class EvidenceError(AssayError):
    """Logs or evidence are incomplete or inconsistent."""

    exit_code = 5


class JudgeError(AssayError):
    """The judge could not grade a sample."""

    exit_code = 6


class RunError(AssayError):
    """A run could not start, finish or resume."""

    exit_code = 7


ERROR_TYPES = (ConfigError, DataError, EvidenceError, JudgeError, RunError)
