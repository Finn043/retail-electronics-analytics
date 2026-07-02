PYTHON ?= python3
RAW ?= data/raw/Electronics_5.json
LIMIT ?= 250000

.PHONY: run model excel dashboard clean

run:
	$(PYTHON) -m src.pipeline --input $(RAW) --limit $(LIMIT)

model:
	$(PYTHON) -m src.export_model --input $(RAW) --limit $(LIMIT)

excel:
	$(PYTHON) -m src.export_excel

dashboard:
	$(PYTHON) -m src.build_dashboard

clean:
	rm -f data/processed/*.csv data/marts/*.csv data/model/*.csv reports/*.md reports/*.xlsx dashboard/index.html
