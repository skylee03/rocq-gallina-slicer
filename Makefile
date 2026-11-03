.PHONY: test selftest demo install-metarocq

test:
	python3 -m unittest discover -s tests -v

selftest:
	python3 selftest.py

demo:
	./run.sh

install-metarocq:
	./scripts/install-metarocq.sh
