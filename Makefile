GLYPHS_FILE=Qalmi_Borna_Simon.glyphs
FINAL_FONT=Qalmi_Borna-Regular.ttf
export PYTHONPATH=.
FEA_FILES=fea-bits/decomposition.fea fea-bits/connections.fea fea-bits/bariye-drop.fea fea-bits/anchor-attachment.fea fea-bits/repositioning.fea fea-bits/bariye-overhang.fea

.DELETE_ON_ERROR:

master_ttf/Qalmi_Borna-Regular.ttf: features.fea $(GLYPHS_FILE)
	fontmake --master-dir . -g $(GLYPHS_FILE) -o ttf

features.fea: $(FEA_FILES)
	# python3 fixup-glyphs-file.py $(GLYPHS_FILE) features.fea
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

fea-bits/bariye-drop.fea: fee/bariye-drop.fee $(GLYPHS_FILE) fee/shared.fee
	fee2fea -O0 $(GLYPHS_FILE) $< > $@

fea-bits/anchor-attachment.fea: fee/anchor-attachment.fee anchors.fee
	fee2fea -O0 $(GLYPHS_FILE) $< > $@

fea-bits/repositioning.fea: fee/repositioning.fee fee/shared.fee
	fee2fea -O0 $(GLYPHS_FILE) $< > $@

fea-bits/bariye-overhang.fea: fee/bariye-overhang.fee $(GLYPHS_FILE) fee/shared.fee
	fee2fea -O0 $(GLYPHS_FILE) $< > $@

