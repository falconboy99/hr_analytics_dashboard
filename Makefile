# Rebuild everything from scratch: data -> dashboard -> report.
PY ?= python3
DB ?= hr_analytics

all: data dashboard report

data:
	$(PY) scripts/generate_data.py

dashboard:
	$(PY) scripts/build_dashboard.py

report:
	$(PY) scripts/build_report.py

# Load into PostgreSQL and run every analysis script
sql:
	createdb $(DB) 2>/dev/null || true
	for f in sql/0*.sql; do psql -d $(DB) -v ON_ERROR_STOP=1 -f $$f || exit 1; done

.PHONY: all data dashboard report sql
