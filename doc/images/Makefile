TARGETS = processing_pipeline_overview.png \
		  giantsquid.png

all: $(TARGETS)

%.png: %.dot
	dot -Tpng $< > $@
