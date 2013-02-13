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
 

from Rule import Rule
from webcolors.webcolors import whatever_to_cairo as colorparser
from webcolors.webcolors import cairo_to_hex
from Eval import Eval

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
    return "{(%s) : [%s] }\n"%(self.ruleChains, self.styles)
  def __init__(self, scalepair):
    self.ruleChains = [[],]
    self.styles = []
    self.eval_type = type(Eval())
    self.scalepair = scalepair
    self.rcpos=0
    self.stylepos=0


  def get_numerics(self):
    """
    Returns a set of number-compared values.
    """
    a = set()
    for c in self.ruleChains:
      for r in c:
        a.update(r.get_numerics())
    a.discard(False)
    return a

  def get_interesting_tags(self, type, zoom):
    """
    Returns a set of tags that were used in here.
    """
    ### FIXME
    a = set()
    for c in self.ruleChains:
      for r in c:
        a.update(r.get_interesting_tags(type, zoom))
    if a:   ## FIXME: semi-illegal optimization, may wreck in future on tagless matches
      
      for r in self.styles:
        for c,b in r.iteritems():
          if __builtins__["type"](b) == self.eval_type:
            a.update(b.extract_tags())
    return a

  def get_sql_hints(self, type, zoom):
    """
    Returns a set of tags that were used in here in form of SQL-hints.
    """
    a = set()
    b = ""
    needed = set(["width", "casing-width", "fill-color", "fill-image", "icon-image", "text", "extrude", "background-image", "background-color", "pattern-image", "shield-text"])
    
    if not needed.isdisjoint(set(self.styles[0].keys())):
      for c in self.ruleChains:
        for r in c:
          p = r.get_sql_hints(type, zoom)
          if p:
            q = "("+p[1] + ")"#[t[1] for t in p]
            if q == "()":
              q = ""
            if b and q:
              b += " OR "+ q
            else:
              b = q
            a.update(p[0])
    # no need to check for eval's
    return a,b
    
  # // Update the current StyleList from this StyleChooser

  def updateStyles(self, sl, ftype, tags, zoom, scale, zscale):
                  # Are any of the ruleChains fulfilled?
                  object_id = False
                  for c in self.ruleChains:
                    object_id = self.testChain(c,ftype,tags,zoom)
                    if object_id:
                      break
                  else:
                    return sl
                  w = 0
                  for r in self.styles:
                    ra = {}
                    for a,b in r.iteritems():
                      "calculating eval()'s"
                      if type(b) == self.eval_type:
                        combined_style = {}
                        for t in sl:
                          combined_style.update(t)
                        for p,q in combined_style.iteritems():
                          if "color" in p:
                            combined_style[p] = cairo_to_hex(q)
                        b = b.compute(tags, combined_style, scale, zscale)
                      ra[a] = b
                    r = ra
                    ra = {}
                    for a, b in r.iteritems():
                      "checking and nicifying style table"
                      if "color" in a:
                        "parsing color value to 3-tuple"
                        ra[a] = colorparser(b)
                      elif any(x in a for x in ("width", "z-index", "opacity", "offset", "radius", "extrude")):
                        "these things are float's or not in table at all"
                        try:
                          ra[a] = float(b)
                        except ValueError:
                          pass
                      elif "dashes" in a:
                        "these things are arrays of float's or not in table at all"
                        try:
                          b = b.split(",")
                          b = [float(x) for x in b]
                          ra[a]= b
                        except ValueError:
                          pass
                      else:
                        ra[a]=b
                    ra["layer"] = float(tags.get("layer",0))*2000+ra.get("z-index",1) # calculating z-index
                    for k,v in ra.items():  # if a value is empty, we don't need it - renderer will do as default.
                        if not v:
                            del ra[k]
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
                        if x.get("object-id") == ra["object-id"]:
                            x.update(ra)
                            break
                    else:
                        if not hasall:
                            allinit.update(ra)
                            sl.append(allinit)
                 # 
                  return sl

  def testChain(self,chain, obj, tags, zoom):
    """
    Tests an object against a chain
    """
    ### FIXME: total MapCSS misreading
    for r in chain:
      return r.test(obj,tags,zoom)
    return False


  def newGroup(self):
    """
    starts a new ruleChain in this.ruleChains
    """
    if self.ruleChains[self.rcpos]: 
        self.ruleChains.append([])


  def newObject(self,e=''):
    """
    adds into the current ruleChain (starting a new Rule)
    """
    rule = Rule(e)
    rule.minZoom=float(self.scalepair[0])
    rule.maxZoom=float(self.scalepair[1])
    self.ruleChains[self.rcpos].append(rule)

  def addZoom(self,z):
    """
    adds into the current ruleChain (existing Rule)
    """

    self.ruleChains[self.rcpos][-1].minZoom=float(z[0])
    self.ruleChains[self.rcpos][-1].maxZoom=float(z[1])


  def addCondition(self,c):
    """
    adds into the current ruleChain (existing Rule)
    """
    self.ruleChains[self.rcpos][-1].conditions.append(c)


  def addStyles(self, a):
    """
    adds to this.styles
    """
    rb = []
    for r in a:
      ra = {}
      for a,b in r.iteritems():
        a = a.strip()
        b = b.strip()
        if a == "casing-width":
          "josm support"
          if b[0] == "+":
            try:
              b = str(float(b)/2)
            except:
              pass
        if "text" == a[-4:]:
          if b[:5] != "eval(":
            b = "eval(tag(\""+b+"\"))"
        if b[:5] == "eval(":
          b = Eval(b)
        ra[a] = b
      rb.append(ra)
   # print rb
    self.styles = self.styles + rb
