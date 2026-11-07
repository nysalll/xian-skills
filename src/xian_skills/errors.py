"""Stable errors and process exit codes."""


class XianError(Exception):
    def __init__(self, message, code=1, payload=None):
        super().__init__(message)
        self.code = code
        self.payload = payload or {}


class NeedConfirm(XianError):
    def __init__(self, message, payload=None):
        super().__init__(message, code=4, payload=payload)


class EnvError(XianError):
    def __init__(self, message, payload=None):
        super().__init__(message, code=2, payload=payload)
