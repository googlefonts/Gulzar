from glyphtools import get_beziers, get_glyph_metrics
from beziers.point import Point
from beziers.line import Line
from itertools import product
import logging

logger = logging.getLogger("NastaliqKerning")

bezier_cache = {}
metrics_cache = {}
min_bubble = 0

from kurbopy import BezPath, TranslateScale, Point, Vec2, Line
from itertools import product
glyphcache = {}

def get_beziers_new(font, glyph):
    if glyph in glyphcache:
        return glyphcache[glyph]
    glyphset = {k: font.default_master.get_glyph_layer(k) for k in font.exportedGlyphs()}
    layer = font.default_master.get_glyph_layer(glyph)
    rv = BezPath.fromDrawable(layer, glyphset)
    glyphcache[glyph] = rv
    return rv


def horizontal_distance(p1, p2):
    min_dist = None
    lowest = None

    miny = int(max(p1.bounding_box().min_y(), p2.bounding_box().min_y()))
    maxy = int(min(p1.bounding_box().max_y(), p2.bounding_box().max_y()))
    for y in range(miny, maxy, 5):
        line = Line(Point(0, y), Point(2000,y))
        i1 = p1.intersections(line)
        i2 = p2.intersections(line)
        if i1 and i2:
            local_min = min(a.distance(b) for a,b in product(i1, i2))
            if local_min is not None and (min_dist is None or local_min < min_dist):
                min_dist = local_min
                lowest = (y,[(l.x,l.y) for l in i1],[(l.x,l.y) for l in i2])
    return min_dist, lowest


def determine_kern(
    font, glyph1, glyph2, targetdistance, offset1=(0, 0), offset2=(0, 0), maxtuck=0.4,
):
    paths1 = get_beziers_new(font, glyph1)
    paths2 = get_beziers_new(font, glyph2)
    metrics1 = get_glyph_metrics(font, glyph1)
    metrics2 = get_glyph_metrics(font, glyph2)

    offset1 = TranslateScale.translate(Vec2(*offset1))
    offset2 = Vec2(offset2[0] + metrics1["width"], offset2[1])
    kern = 0
    last_best = None

    minimum_possible = -1000
    full_width = max(metrics1["run"] - min(0, metrics1["rsb"]), min_bubble)
    logger.debug("Full width of %s is %i" % (glyph1, full_width))
    if maxtuck:
        maximum_width = full_width * maxtuck
        logger.debug("Maximum distance into %s is %i" % (glyph1, maximum_width))
        logger.debug("Left edge of %s is %i" % (glyph2, metrics2["xMin"]))
        minimum_possible = -metrics2["xMin"] - maximum_width
        logger.debug("Biggest kern is %i" % minimum_possible)

    iterations = 0
    # Compute min distance
    min_distance = None
    for p1 in paths1:
        moved_p1 = offset1 * p1
        for p2 in paths2:
            t2 = TranslateScale.translate(offset2 + Vec2(kern, 0))
            moved_p2 = t2 * p2
            d,debuginfo = horizontal_distance(moved_p1, moved_p2)
            # d = cached_distance(p1, p2)
            if d is None:
                logger.debug("d was None")
            else:
                logger.debug("d was %i at %i (%s, %s)" % (d, *debuginfo))
            # logger.debug("offset1 was %s" % offset1)
            # logger.debug("offset2 was %s" % offset2)
            if d is not None and (min_distance is None or d < min_distance):
                min_distance = d
    if min_distance is None:
        return minimum_possible
    kern = kern + (targetdistance - min_distance)
    if kern < minimum_possible:
        return minimum_possible
    #     kern = kern -  metrics1["rsb"]
    if maxtuck:
        kern = max(kern, -(metrics1["xMax"] * (1 + maxtuck)) + metrics1["rsb"])
    else:
        kern = max(kern, -(metrics1["xMax"]) + metrics1["rsb"])
    if metrics1["rsb"] < 0:
        kern = kern - metrics1["rsb"]
    logger.debug("%s/%s/%i = %i" % (glyph1, glyph2, offset2.y, kern))
    return kern  # int(kern)
