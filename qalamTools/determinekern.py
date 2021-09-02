from glyphtools import get_beziers, get_glyph_metrics
import logging

logger = logging.getLogger("NastaliqKerning")

bezier_cache = {}
metrics_cache = {}
distance_cache = {}
min_bubble = 250


def determine_kern_old(
    font,
    glyph1,
    glyph2,
    targetdistance,
    offset1=(0, 0),
    offset2=(0, 0),
    maxtuck=0.4,
):
    """Determine a kerning value required to set two glyphs at given ink-to-ink distance.

    The value is bounded by the ``maxtuck`` parameter. For example, if
    ``maxtuck`` is 0.20, the right glyph will not be placed any further
    left than 80% of the width of left glyph, even if this places the
    ink further than ``targetdistance`` units away.

    Args:
        font: a ``fontTools`` TTFont object or a ``glyphsLib`` GSFontMaster
              object OR a ``babelfont`` Font object.
        glyph1: name of the left glyph.
        glyph2: name of the right glyph.
        targetdistance: distance to set the glyphs apart.
        offset1: offset (X-coordinate, Y-coordinate) to place left glyph.
        offset2: offset (X-coordinate, Y-coordinate) to place right glyph.
        maxtuck: maximum proportion of the left glyph's width to kern.

    Returns: A kerning value, in units.
    """
    def cached_distance(p1, p2):
        if (p1, p2) not in distance_cache:
            distance_cache[(p1, p2)] = p1.distanceToPath(p2, samples=3)
        return distance_cache[(p1, p2)]

    paths1 = get_beziers(font, glyph1)
    paths2 = get_beziers(font, glyph2)
    metrics1 = get_glyph_metrics(font, glyph1)
    metrics2 = get_glyph_metrics(font, glyph2)

    offset1 = Point(*offset1)
    offset2 = Point(offset2[0] + metrics1["width"], offset2[1])
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
    while True:
        # Compute min distance
        min_distance = None
        for p1 in paths1:
            p1 = p1.clone().translate(offset1)
            for p2 in paths2:
                p2 = p2.clone().translate(Point(offset2.x + kern, offset2.y))
                d = p1.distanceToPath(p2, samples=3)
                #d = cached_distance(p1, p2)
#                 logger.debug("d was", d)
                #logger.debug("offset1 was %s" % offset1)
                #logger.debug("offset2 was %s" % offset2)
                if not min_distance or d[0] < min_distance:
                    min_distance = d[0]
        if not last_best or min_distance < last_best:
            last_best = min_distance
        else:
            break  # Nothing helped
        if abs(min_distance - targetdistance) < 1 or iterations > 10:
            break
        iterations = iterations + 1
        kern = kern + (targetdistance - min_distance)
        if kern < minimum_possible:
            return minimum_possible
#     kern = kern -  metrics1["rsb"]
    if maxtuck:
        kern = max(kern, -(metrics1["xMax"] * (1+maxtuck)) + metrics1["rsb"])
    else:
        kern = max(kern, -(metrics1["xMax"]) + metrics1["rsb"])
    if metrics1["rsb"] < 0:
        kern = kern -  metrics1["rsb"]
    logger.debug("%s/%s/%i = %i" % (glyph1, glyph2, offset2.y, kern))
    return int(kern)

try:
    from kurbopy import BezPath, TranslateScale, Point, Vec2
    glyphcache = {}

    def get_beziers_new(font, glyph):
        if glyph in glyphcache:
            return glyphcache[glyph]
        glyphset = {k: font.default_master.get_glyph_layer(k) for k in font.exportedGlyphs()}
        layer = font.default_master.get_glyph_layer(glyph)
        rv = BezPath.fromDrawable(layer, glyphset)
        glyphcache[glyph] = rv
        return rv


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
        while True:
            # Compute min distance
            min_distance = None
            for p1 in paths1:
                moved_p1 = offset1 * p1
                for p2 in paths2:
                    t2 = TranslateScale.translate(offset2 + Vec2(kern, 0))
                    moved_p2 = t2 * p2
                    d = moved_p1.min_distance(moved_p2)
                    # d = cached_distance(p1, p2)
                    #                 logger.debug("d was", d)
                    # logger.debug("offset1 was %s" % offset1)
                    # logger.debug("offset2 was %s" % offset2)
                    if not min_distance or d < min_distance:
                        min_distance = d
            if not last_best or min_distance < last_best:
                last_best = min_distance
            else:
                break  # Nothing helped
            if abs(min_distance - targetdistance) < 1 or iterations > 10:
                break
            iterations = iterations + 1
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
        # logger.debug("%s/%s/%i = %i" % (glyph1, glyph2, offset2.y, kern))
        return kern  # int(kern)
except Exception as e:
    determine_kern = determine_kern_old
