PYTHON ?= python3
RAW ?= data/raw/Electronics_5.json
LIMIT ?= 250000

.PHONY: run dashboard clean

run:
	$(PYTHON) -m src.pipeline --input $(RAW) --limit $(LIMIT)

dashboard:
	$(PYTHON) -m src.build_dashboard

clean:
	rm -f data/processed/*.csv data/marts/*.csv reports/*.md dashboard/index.html
