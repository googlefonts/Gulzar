GLYPHS_FILE=Gulzar.glyphs
FINAL_FONT=master_ttf/Gulzar-Regular.ttf
export PYTHONPATH=.:/Users/simon/hacks/typography/fontFeatures/:/Users/simon/hacks/bezier-things/beziers.py:/Users/simon/hacks/typography/glyphtools/:
export FONTTOOLS_LOOKUP_DEBUGGING=1
FEA_FILES=fea-bits/languagesystem.fea fea-bits/decomposition.fea fea-bits/connections.fea fea-bits/bariye-drop.fea fea-bits/anchor-attachment.fea fea-bits/kerning.fea fea-bits/post-mkmk-repositioning.fea fea-bits/bariye-overhang.fea

.DELETE_ON_ERROR:

$(FINAL_FONT): features.fea $(GLYPHS_FILE)
	fontmake -f --master-dir . -g $(GLYPHS_FILE) --no-production-names -o ttf --output-path $(FINAL_FONT)
	fonttools feaLib -o $(FINAL_FONT) features.fea $(FINAL_FONT)

replace: features.fea
	fonttools feaLib -o $(FINAL_FONT) features.fea $(FINAL_FONT)

fix: $(FINAL_FONT)
	gftools-fix-font.py --include-source-fixes -o $(FINAL_FONT) $(FINAL_FONT)

features.fea: $(FEA_FILES)
	cat $^ > features.fea

clean:
	rm -f $(FINAL_FONT) features.fea rules.csv fea-bits/*

specimen: specimen/specimen.pdf

rules.csv: $(GLYPHS_FILE)
	python3 dump-glyphs-rules.py $(GLYPHS_FILE) > rules.csv

test: $(FINAL_FONT)
	fontbakery check-profile qa/fontbakery-shaping.py $(FINAL_FONT)

testproof: $(FINAL_FONT) regressions.txt
	gnipahs $(FINAL_FONT) regressions.txt

proof: $(FINAL_FONT) qa/urdu-john.sil
	sile qa/urdu-john.sil

specimen/specimen.pdf: $(FINAL_FONT) specimen/specimen.sil
	cd specimen ; sile specimen.sil

fea-bits/languagesystem.fea: fee/languages.fee
	fee2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

fea-bits/decomposition.fea: fee/decomposition.fee
	fee2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

fea-bits/connections.fea: fee/connections.fee rules.csv
	fee2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

fea-bits/anchor-attachment.fea: fee/anchor-attachment.fee fee/pre-mkmk-repositioning.fee
	fee2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

fea-bits/kerning.fea: fee/kerning.fee fee/shared.fee
	fee2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

fea-bits/post-mkmk-repositioning.fea: fee/post-mkmk-repositioning.fee fee/shared.fee
	fee2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

# Technically these two should depend on the Glyphs file, but since the design
# and width of glyphs is mostly fixed, I'm removing that dependency for now.
fea-bits/bariye-drop.fea: fee/bariye-drop.fee fee/shared.fee
	fee2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@

fea-bits/bariye-overhang.fea: fee/bariye-overhang.fee fee/shared.fee
	fee2fea --omit-gdef -O0 $(GLYPHS_FILE) $< > $@
