# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

from collections import Iterable, MutableMapping
import inspect
import six
from parsel import Selector

from .filters import through
from .parsers import First
from .utils import merge_dict


class BaseElement(object):
    filter = (through,)

    def __init__(self, xpath=None, filter=None):
        self.instance = None
        self.xpath = xpath
        if filter:
            self.filter = filter

    def __get__(self, instance, owner):
        self.instance = instance
        return self

    @property
    def is_descriptor(self):
        return self.instance is not None

    def get_function(self, fn):
        if callable(fn):
            return fn

        method = getattr(self, six.text_type(fn), None)
        if method and callable(method):
            return method

        if self.instance and hasattr(self.instance, 'get_function'):
            return self.instance.get_function(fn)

        raise ValueError('{} is not callable.'.format(fn))

    def get_filter(self):
        if not isinstance(self.filter, (list, tuple)):
            filters = [self.filter]
        else:
            filters = self.filter

        return [self.get_function(f) for f in filters]

    def get_selector(self, html):
        selector = Selector(text=html) if isinstance(html, str) else html
        if self.xpath:
            return selector.xpath(self.xpath)
        return selector.xpath('.')

    def parse(self, html):
        selector = self.get_selector(html)
        if len(selector) == 0:
            return None

        value = self._parse(selector)
        for filter in self.get_filter():
            value = filter(value)

        return value

    def _parse(self, selector):
        raise NotImplementedError()


class ContentMeta(type):
    def __new__(klass, name, bases, attrs):
        new_class = super(ContentMeta, klass).__new__(klass, name, bases, attrs)

        fields = {
            attr: getattr(new_class, attr)
            for attr in attrs
            if not attr.startswith('_') and isinstance(getattr(new_class, attr), BaseElement)
        }

        for base in bases:
            if hasattr(base, 'fields'):
                fields = merge_dict(base.fields, fields)

        new_class.fields = fields

        return new_class


@six.add_metaclass(ContentMeta)
class Content(BaseElement):
    def _parse(self, selector):
        return {
            name: getattr(self, name).parse(selector)
            for name in self.fields
        }

    def parse(self, html, object=None):
        data = super(Content, self).parse(html)
        if object is None:
            return data

        if inspect.isclass(object):
            object = object()

        if isinstance(object, MutableMapping):
            for key, value in data.items():
                object[key] = value
            return object

        for key, value in data.items():
            setattr(object, key, value)
        return object


class Element(BaseElement):
    parser = First()

    def __init__(self, *args, **kwargs):
        parser = kwargs.pop('parser', None)
        if parser:
            self.parser = parser
        super(Element, self).__init__(*args, **kwargs)

    def get_parser(self):
        return self.get_function(self.parser)

    def _parse(self, selector):
        return self.get_parser()(selector)
