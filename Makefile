GLYPHS_FILE=Qalmi_Borna_Simon.glyphs
FINAL_FONT=Qalmi_Borna-Regular.ttf
export PYTHONPATH=.:/Users/simon/hacks/typography/fontFeatures
export FONTTOOLS_DEBUG=1
FEA_FILES=fea-bits/decomposition.fea fea-bits/connections.fea fea-bits/bariye-drop.fea fea-bits/anchor-attachment.fea fea-bits/post-mkmk-repositioning.fea fea-bits/bariye-overhang.fea

.DELETE_ON_ERROR:

master_ttf/Qalmi_Borna-Regular.ttf: features.fea $(GLYPHS_FILE)
	fontmake --master-dir . -g $(GLYPHS_FILE) -o ttf

features.fea: $(FEA_FILES)
	cat $^ > features.fea

clean:
	rm -f master_ttf/Qalmi_Borna-Regular.ttf features.fea anchors.fee rules.csv

anchors.fee: $(GLYPHS_FILE)
	python3 dump-fee-anchors.py $(GLYPHS_FILE) > anchors.fee

rules.csv: $(GLYPHS_FILE)
	python3 dump-glyphs-rules.py $(GLYPHS_FILE) > rules.csv

test: master_ttf/$(FINAL_FONT) regressions.txt
	fontbakery check-profile -m FAIL -v ./gnipahs.py master_ttf/$(FINAL_FONT)

testproof: master_ttf/$(FINAL_FONT) regressions.txt
	gnipahs master_ttf/$(FINAL_FONT) regressions.txt

proof: master_ttf/$(FINAL_FONT) urdu-john.sil
	sile urdu-john.sil

fea-bits/decomposition.fea: fee/decomposition.fee
	fee2fea -O0 $(GLYPHS_FILE) $< > $@

fea-bits/connections.fea: fee/connections.fee rules.csv
	fee2fea -O0 $(GLYPHS_FILE) $< > $@

fea-bits/anchor-attachment.fea: fee/anchor-attachment.fee anchors.fee fee/pre-mkmk-repositioning.fee
	fee2fea -O0 $(GLYPHS_FILE) $< > $@

fea-bits/post-mkmk-repositioning.fea: fee/post-mkmk-repositioning.fee fee/shared.fee
	fee2fea -O0 $(GLYPHS_FILE) $< > $@

# Technically these two should depend on the Glyphs file, but since the design
# and width of glyphs is mostly fixed, I'm removing that dependency for now.
fea-bits/bariye-drop.fea: fee/bariye-drop.fee fee/shared.fee
	fee2fea -O0 $(GLYPHS_FILE) $< > $@

fea-bits/bariye-overhang.fea: fee/bariye-overhang.fee fee/shared.fee
	fee2fea -O0 $(GLYPHS_FILE) $< > $@
