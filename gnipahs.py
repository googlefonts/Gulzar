from fontbakery.callable import check, condition
from fontbakery.checkrunner import (DEBUG, PASS,
               INFO, SKIP, WARN, FAIL, ERROR)
from fontbakery.fonts_profile import profile_factory
import os
import re

def gnipahs_file(font):
  return os.path.join(os.path.dirname(font), "gnipahs.txt")

@condition
def has_gnipahs_file(font):
  return os.path.exists(gnipahs_file(font))

@condition
def has_vharfbuzz():
  try:
    from vharfbuzz import Vharfbuzz
  except ImportError as e:
    return False
  return True

@condition
def has_collidoscope():
  try:
    from collidoscope import Collidoscope
  except ImportError as e:
    return False
  return True

@condition
def has_stringbrewer():
  try:
    from stringbrewer import StringBrewer
  except ImportError as e:
    return False
  return True

@check(id='uk.co.corvelsoftware/gnipahs',
  conditions=["has_gnipahs_file", "has_vharfbuzz", "has_collidoscope", "has_stringbrewer"])
def shaping_test(font):
  """Test shaping output"""
  from vharfbuzz import Vharfbuzz
  from collidoscope import Collidoscope
  from stringbrewer import StringBrewer
  vhb = Vharfbuzz(font)
  col = Collidoscope(font, {
          "cursive": True,
          "marks": True,
          "faraway": True,
          "adjacentmarks": False,
          # "area": 0,
      },
  )
  tests = []
  ingredients = []
  seen_blank = False

  with open(gnipahs_file(font), "r") as testfile:
      for line in testfile.read().split("\n"):
          if re.match(r"^\s*#", line):
              continue
          if line == "":
              seen_blank = True
          if seen_blank:
              ingredients.append(line)
          else:
              elements = line.split(":")
              if elements[0].startswith('"') and elements[0].endswith('"'):
                  tests.append(
                      {
                          "type": "literal",
                          "string": elements[0][1:-1],
                          "options": elements[1:],
                      }
                  )
              else:
                  tests.append(
                      {"type": "pattern", "string": elements[0], "options": elements[1:]}
                  )

  expanded_tests = []
  for test in tests:
    if test["type"] == "pattern":
        b = StringBrewer(from_string=test["string"] + "\n" + "\n".join(ingredients))
        try:
            for s in b.generate_all():
                expanded_tests.append( (s, test["options"]) )
        except Exception as e:
            for i in range(1, 1000):
                expanded_tests.append( (b.generate(), test["options"]) )
    if test["type"] == "literal":
        expanded_tests.append( (test["string"], test["options"]) )

  for string, options in expanded_tests:
    glyphs = col.get_glyphs(string)
    collisions = col.has_collisions(glyphs)
    if collisions:
        yield(FAIL, "Overlaps found in %s" % string)
    else:
        yield(PASS, "No overlaps found in %s" % string)
    if len(test["options"]) > 0:
        buf = vhb.shape(string)
        expected = options[0]
        got = vhb.serialize_buf(buf)
        if expected == got:
            yield(PASS, "%s shaped as expected" % string)
        else:
            yield(FAIL, "shaping text for %s: expected %s got %s" % (string, expected, got))
