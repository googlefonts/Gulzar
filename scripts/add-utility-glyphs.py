# Add utility glyphs to Glyphs file
import glyphsLib
import argparse
import copy

parser = argparse.ArgumentParser(description='Add utility glyphs to Glyphs file')
parser.add_argument('file', help='Glyphs file to add utility glyphs to')
parser.add_argument('output', help='Glyphs file to save')

args = parser.parse_args()

BARIYE_DROP = 120

gsfont = glyphsLib.load(open(args.file))

yb_marks = ["sdb.yb", "ddb.yb", "tdb.yb", "haydb.yb"]
for yb_mark in yb_marks:
    if yb_mark in gsfont.glyphs:
        mark_glyph = gsfont.glyphs[yb_mark]
    else:
        mark_glyph = glyphsLib.GSGlyph(yb_mark)
        orig_glyph = gsfont.glyphs[yb_mark[:-3]]
        for layer in orig_glyph.layers:
            new_layer = glyphsLib.GSLayer()
            new_layer.layerId = layer.layerId
            new_layer.associatedMasterId = layer.associatedMasterId
            new_layer.components = [glyphsLib.GSComponent(orig_glyph, (-layer.width/2,-BARIYE_DROP))]
            new_layer.width = 0
            mark_glyph.layers.append(new_layer)
        mark_glyph.category = "Mark"
        mark_glyph.storeCategory = True
        mark_glyph.subCategory = "Nonspacing"
        mark_glyph.storeSubCategory = True
        gsfont.glyphs.append(mark_glyph)
    collides = yb_mark+".collides"
    if collides not in gsfont.glyphs:
        print("Adding ",collides)
        collides_glyph = glyphsLib.GSGlyph(collides)
        for layer in mark_glyph.layers:
            new_layer = glyphsLib.GSLayer()
            new_layer.layerId = layer.layerId
            new_layer.associatedMasterId = layer.associatedMasterId
            new_layer.components = [glyphsLib.GSComponent(mark_glyph, (0,0))]
            new_layer.width = 0
            collides_glyph.layers.append(new_layer)
        collides_glyph.category = "Mark"
        collides_glyph.storeCategory = True
        collides_glyph.subCategory = "Nonspacing"
        collides_glyph.storeSubCategory = True
        gsfont.glyphs.append(collides_glyph)

below_marks = ["sdb", "ddb", "tdb", "haydb", "sda", "dda", "tda", "toeda"]
for mark in below_marks:
    for suffix in ["one", "two"]:
        gname = mark+"."+suffix
        if gname in gsfont.glyphs:
            continue
        print("Adding ",gname)
        mark_glyph = glyphsLib.GSGlyph(gname)
        orig_glyph = gsfont.glyphs[mark]
        for layer in orig_glyph.layers:
            new_layer = glyphsLib.GSLayer()
            new_layer.layerId = layer.layerId
            new_layer.associatedMasterId = layer.associatedMasterId
            new_layer.components = [glyphsLib.GSComponent(orig_glyph, (0,0))]
            new_layer.width = 0
            mark_glyph.layers.append(new_layer)
            # Copy mkmk anchors
            if layer.anchors["bottom"]:
                new_layer.anchors.append(copy.copy(layer.anchors["bottom"]))
            if layer.anchors["top"]:
                new_layer.anchors.append(copy.copy(layer.anchors["top"]))
            # Copy suffixed _ anchor
            if layer.anchors["_bottom"]:
                other_anchor = copy.copy(layer.anchors["_bottom"])
                other_anchor.name = "_bottom."+suffix
                new_layer.anchors.append(other_anchor)
            if layer.anchors["_top"]:
                other_anchor = copy.copy(layer.anchors["_top"])
                other_anchor.name = "_top."+suffix
                new_layer.anchors.append(other_anchor)
            if layer.anchors["_comma"]:
                other_anchor = copy.copy(layer.anchors["_comma"])
                other_anchor.name = "_comma."+suffix
                new_layer.anchors.append(other_anchor)
        mark_glyph.category = "Mark"
        mark_glyph.storeCategory = True
        mark_glyph.subCategory = "Nonspacing"
        mark_glyph.storeSubCategory = True
        gsfont.glyphs.append(mark_glyph)


gsfont.format_version = 3 # Save as v3 to let Rust read it
gsfont.save(args.output)
