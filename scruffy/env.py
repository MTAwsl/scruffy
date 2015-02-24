import os
import yaml
import itertools
import errno
import logging
import logging.config

from .directory import Directory
from .plugin import PluginManager
from .config import ConfigNode, Config, ConfigEnv, ConfigApplicator


class Environment(object):
    """
    An environment in which to run a program
    """
    def __init__(self, setup_logging=True, *args, **kwargs):
        self._pm = PluginManager()
        self._children = kwargs
        self.config = None

        # find a config if we have one and load it
        self.config = self.find_config(kwargs)
        if self.config:
            self.config.load()

        # setup logging
        if setup_logging:
            d = self.config.logging.dict_config.to_dict()
            if d:
                # configure logging from the configuration
                logging.config.dictConfig(d)
            else:
                # no dict config, set up a basic config so we at least get messages logged to stdout
                log = logging.getLogger()
                log.setLevel(logging.INFO)
                if len(filter(lambda h: isinstance(h, logging.StreamHandler), log.handlers)) == 0:
                    log.addHandler(logging.StreamHandler())

        # initialise children
        for key in self._children:
            # if it's a string, assume it's a directory
            if type(self._children[key]) == str:
                self._children[key] = Directory(self._children[key])

            # set this environment as the child's env
            self._children[key]._env = self

            # apply config and prepare
            self._children[key].apply_config(ConfigApplicator(self.config))
            self._children[key].prepare()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.cleanup()

    def __getitem__(self, key):
        return self._children[key]

    def __getattr__(self, key):
        return self._children[key]

    def find_config(self, children):
        """
        Find a config in our children so we can fill in variables in our other
        children with its data.
        """
        # first see if we got a kwarg named 'config', as this guy is special
        if 'config' in children:
            if type(children['config']) == str:
                children['config'] = ConfigFile(children['config'])
            elif isinstance(children['config'], Config):
                children['config'] = children['config']
            elif type(children['config']) == dict:
                children['config'] = Config(data=children['config'])
            else:
                raise TypeError("Don't know how to turn {} into a Config".format(type(children['config'])))
            return children['config']

        # next check the other kwargs
        for k in children:
            if isinstance(children[k], Config):
                return children[k]

        # if we still don't have a config, see if there's a directory with one
        for k in children:
            if isinstance(children[k], Directory):
                for j in children[k]._children:
                    if isinstance(children[k]._children[j], Config):
                        return children[k]._children[j]

    def add(self, **kwargs):
        """
        Add objects to the environment.
        """
        for key in kwargs:
            self._children[key] = kwargs[key]
            self._children[key].apply_config(ConfigApplicator(self.config))
            self._children[key].prepare()

    def cleanup(self):
        """
        Clean up the environment
        """
        for key in self._children:
            self._children[key].cleanup()

    @property
    def plugins(self):
        return self._pm.plugins
