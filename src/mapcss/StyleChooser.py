#!/usr/bin/env python
# -*- coding: utf-8 -*-
#    This file is part of kothic, the realtime map renderer.

#   kothic is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.

#   kothic is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.

#   You should have received a copy of the GNU General Public License
#   along with kothic.  If not, see <http://www.gnu.org/licenses/>.


from .Rule import Rule
from .webcolors.webcolors import whatever_to_cairo as colorparser
from .webcolors.webcolors import cairo_to_hex
from .Eval import Eval
from .Condition import  *

TYPE_EVAL = type(Eval())

def make_nice_style(r):
    ra = {}
    for a, b in r.items():
        "checking and nicifying style table"
        if type(b) == TYPE_EVAL:
            ra[a] = b
        elif "color" in a and b.strip() != 'none':
            "parsing color value to 3-tuple"
            # print "res:", b
            if b and (type(b) != tuple):
            # if not b:
            #    print sl, ftype, tags, zoom, scale, zscale
            # else:
                ra[a] = colorparser(b)
            elif b:
                ra[a] = b
        elif any(x in a for x in ("width", "opacity", "offset", "radius", "extrude")):
            "these things are float's or not in table at all"
            try:
                ra[a] = float(b)
            except ValueError:
                pass
        elif "dashes" in a and type(b) != list:
            "these things are arrays of float's or not in table at all"
            try:
                b = b.split(",")
                b = [float(x) for x in b]
                ra[a] = b
            except ValueError:
                ra[a] = []
        else:
            ra[a] = b
    return ra


class StyleChooser:
    """
    A StyleChooser object is equivalent to one CSS selector+declaration.

    Its ruleChains property is an array of all the selectors, which would
    traditionally be comma-separated. For example:
            h1, h2, h3 em
    is three ruleChains.

    Each ruleChain is itself an array of nested selectors. So the above
    example would roughly be encoded as:
            [[h1],[h2],[h3,em]]
              ^^   ^^   ^^ ^^   each of these is a Rule

    The styles property is an array of all the style objects to be drawn
        if any of the ruleChains evaluate to true.
    """
    def __repr__(self):
        return "{(%s) : [%s] }\n" % (self.ruleChains, self.styles)

    def __init__(self, scalepair):
        self.ruleChains = []
        self.styles = []
        self.eval_type = TYPE_EVAL
        self.scalepair = scalepair
        self.selzooms = None
        self.compatible_types = set()
        self.has_evals = False
        self.has_runtime_conditions = False
        self.cached_tags = None

    def extract_tags(self):
        if self.cached_tags is not None:
            return self.cached_tags
        a = set()
        for r in self.ruleChains:
            a.update(r.extract_tags())
            if "*" in a:
                a = set('*')
                break
        if self.has_evals and "*" not in a:
            for s in self.styles:
                for v in list(s.values()):
                    if type(v) == self.eval_type:
                        a.update(v.extract_tags())
        if len(a) == 0:
            a = set('*')
        self.cached_tags = a
        return a

    def get_runtime_conditions(self, tags):
        if not self.has_runtime_conditions:
            return None

        rule_and_object_id = self.testChains(tags)

        if not rule_and_object_id:
            return None

        rule = rule_and_object_id[0]

        return rule.runtime_conditions

    def updateStyles(self, sl, tags, xscale, zscale, filter_by_runtime_conditions):
        # Are any of the ruleChains fulfilled?
        rule_and_object_id = self.testChains(tags)

        if not rule_and_object_id:
            return sl

        rule = rule_and_object_id[0]
        object_id = rule_and_object_id[1]

        if (filter_by_runtime_conditions is not None
            and rule.runtime_conditions is not None
            and filter_by_runtime_conditions != rule.runtime_conditions):
            return sl

        for r in self.styles:
            if self.has_evals:
                ra = {}
                for a, b in r.items():
                    "calculating eval()'s"
                    if type(b) == self.eval_type:
                        combined_style = {}
                        for t in sl:
                            combined_style.update(t)
                        for p, q in combined_style.items():
                            if "color" in p:
                                combined_style[p] = cairo_to_hex(q)
                        b = b.compute(tags, combined_style, xscale, zscale)
                    ra[a] = b
                ra = make_nice_style(ra)
            else:
                ra = r.copy()

            ra["object-id"] = str(object_id)
            hasall = False
            allinit = {}
            for x in sl:
                if x.get("object-id") == "::*":
                    allinit = x.copy()
                if ra["object-id"] == "::*":
                    oid = x.get("object-id")
                    x.update(ra)
                    x["object-id"] = oid
                    if oid == "::*":
                        hasall = True
                else:
                    if x.get("object-id") == ra["object-id"]:
                        x.update(ra)
                        break
            else:
                if not hasall:
                    allinit.update(ra)
                    sl.append(allinit)

        return sl

    def testChains(self, tags):
        """
        Tests an object against a chain
        """
        for r in self.ruleChains:
            tt = r.test(tags)
            if tt:
                return r, tt
        return False

    def newGroup(self):
        """
        starts a new ruleChain in this.ruleChains
        """
        pass

    def newObject(self, e=''):
        # print "newRule"
        """
        adds into the current ruleChain (starting a new Rule)
        """
        rule = Rule(e)
        rule.minZoom = float(self.scalepair[0])
        rule.maxZoom = float(self.scalepair[1])
        self.ruleChains.append(rule)

    def addZoom(self, z):
        # print "addZoom ", float(z[0]), ", ", float(z[1])
        """
        adds into the current ruleChain (existing Rule)
        """
        self.ruleChains[-1].minZoom = float(z[0])
        self.ruleChains[-1].maxZoom = float(z[1])

    def addCondition(self, c):
        # print "addCondition ", c
        """
        adds into the current ruleChain (existing Rule)
        """
        self.ruleChains[-1].conditions.append(c)

    def addRuntimeCondition(self, c):
        # print "addRuntimeCondition ", c
        """
        adds into the current ruleChain (existing Rule)
        """
        if self.ruleChains[-1].runtime_conditions is None:
            self.ruleChains[-1].runtime_conditions = [c]
            self.has_runtime_conditions = True
        else:
            self.ruleChains[-1].runtime_conditions.append(c)

    def addStyles(self, a):
        # print "addStyle ", a
        """
        adds to this.styles
        """
        for r in self.ruleChains:
            if not self.selzooms:
                self.selzooms = [r.minZoom, r.maxZoom]
            else:
                self.selzooms[0] = min(self.selzooms[0], r.minZoom)
                self.selzooms[1] = max(self.selzooms[1], r.maxZoom)
            self.compatible_types.update(r.get_compatible_types())
        rb = []
        for r in a:
            ra = {}
            for a, b in r.items():
                a = a.strip()
                b = b.strip()
                if a == "casing-width":
                    "josm support"
                    if b[0] == "+":
                        try:
                            b = str(float(b) / 2)
                        except:
                            pass
                if b[:5] == "eval(":
                    b = Eval(b)
                    self.has_evals = True
                ra[a] = b
            ra = make_nice_style(ra)
            rb.append(ra)
        self.styles = self.styles + rb
