#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    WTF override Helper
"""

from copy import copy

from wtforms import SelectField
from wtforms.compat import text_type

__all__ = (
    'BetterSelectField',
    'BetterSelectFieldNonValidating',
    )

class BetterSelectField(SelectField):
    def __init__(self, label=None, validators=None, coerce=text_type, choices=None, **kwargs):
        super(BetterSelectField, self).__init__(label, validators, **kwargs)
        self.coerce = coerce

        # Copy SelectField.choices so each instance can be modified independently
        # cf. https://github.com/wtforms/wtforms/pull/286
        self.choices = copy(choices)

    def iter_choices(self):
        if self.choices and self.data and not self.data == "None" and not self.data in [k for k,v in self.choices]:
            self.choices = self.choices + [(self.data, u'⚠ "%s" not available in choices ⚠' % self.data)]
        for value, label in self.choices:
            yield (value, label, self.coerce(value) == self.data)

class BetterSelectFieldNonValidating(BetterSelectField):
    """
    Non validated select field that accepts dynamic choices added by the browser.
    """
    def pre_validate(self, form):
        pass
