"""Errors raised while reading DeskCard's data files."""


class ConfigError(Exception):
    """The config file could not be read or parsed at all (bad JSON, wrong shape)."""


class SettingsError(Exception):
    """A settings value is malformed and the session cannot be built from it."""
