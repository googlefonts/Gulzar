import csv
from glyphsLib import GSFont
import sys

font = GSFont(sys.argv[1])
conn = font.userData["nastaliqConnections"]

with open('rules.csv', 'w') as outcsv:
  w = csv.DictWriter(outcsv,conn["colnames"])
  w.writeheader()
  w.writerows(conn["rows"])
