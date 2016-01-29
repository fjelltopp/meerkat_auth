"""
config.py

Configuration and settings
"""


class Config(object):
    DEBUG = False
    TESTING = False

    SUBSCRIBERS = 'hermes_subscribers'
    SUBSCRIPTIONS = 'hermes_subscriptions'
    LOG = 'hermes_log'

    SENDER = 'jonathan.s.berry@googlemail.com'
    CHARSET = 'UTF-8'
    FROM = 'Meerkat'

    API_KEY = "test-hermes"

class Production(Config):
    DEBUG = False
    TESTING = False

class Development(Config):
    DEBUG = True
    TESTING = True

class Testing(Config):
    DEBUG = False
    TESTING = True
