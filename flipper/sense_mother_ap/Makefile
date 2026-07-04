# Sense Mother AP — dev conveniences.
#
# Run from this directory. All targets are thin wrappers around
# ufbt / screen / rtl_433; the goal is to stop re-typing the exact
# baud / device / log-path each iteration.

FLIPPER_UART      ?= /dev/cu.usbserial-834220
FLIPPER_BAUD      ?= 230400
FLIPPER_CDC       ?= $(firstword $(wildcard /dev/cu.usbmodemflip*))
SCREEN_SESSION    ?= fliplog
SCREEN_LOG        ?= /tmp/screenlog.0
RTL_FREQ          ?= 915M
RTL_DUR           ?= 30
RTL_HITS          ?= /tmp/cookie_hits.json
REPO_ROOT         := $(shell git rev-parse --show-toplevel 2>/dev/null || echo ../..)

.PHONY: help build launch try monitor monitor-stop monitor-status log tail rtl parse sniff clean full tx sniff-tx rf-probe

WAIT  ?= 45
COUNT ?= 1

help:  ## Show this help
	@awk 'BEGIN{FS=":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build:  ## ufbt (build fap)
	ufbt

launch:  ## ufbt launch (build + sideload + start on Flipper)
	ufbt launch

try:  ## Build+launch, then wait WAIT seconds (default $(WAIT)) and dump the new log lines
	@before=$$(wc -c < $(SCREEN_LOG) 2>/dev/null || echo 0); \
		ufbt launch 2>&1 | tail -3; \
		echo "--- waiting $(WAIT)s for on-air events (rebuild+deploy already counted) ..."; \
		sleep $(WAIT); \
		after=$$(wc -c < $(SCREEN_LOG) 2>/dev/null || echo 0); \
		echo "log grew: $$((after - before)) bytes"; \
		grep -a SenseMotherAP $(SCREEN_LOG) | tail -20

full: monitor launch  ## Start monitor + launch app (idempotent)

monitor:  ## Start detached screen tail of Flipper UART -> $(SCREEN_LOG)
	@if screen -ls | grep -q "\.$(SCREEN_SESSION)\b"; then \
		echo "screen session '$(SCREEN_SESSION)' already running — see 'make monitor-status'"; \
	else \
		rm -f $(SCREEN_LOG); \
		cd /tmp && screen -dmS $(SCREEN_SESSION) -L $(FLIPPER_UART) \
			$(FLIPPER_BAUD),cs8,-parenb,-cstopb,-hupcl; \
		echo "started screen '$(SCREEN_SESSION)' logging to $(SCREEN_LOG)"; \
	fi

monitor-stop:  ## Kill the detached screen session
	@screen -X -S $(SCREEN_SESSION) quit 2>/dev/null && \
		echo "stopped '$(SCREEN_SESSION)'" || \
		echo "no session '$(SCREEN_SESSION)' to stop"

monitor-status:  ## Show screen session state + log size
	@screen -ls | grep "\.$(SCREEN_SESSION)\b" || echo "no '$(SCREEN_SESSION)' session"
	@ls -la $(SCREEN_LOG) 2>/dev/null || true

log:  ## Show recent SenseMotherAP lines from the log
	@grep -a SenseMotherAP $(SCREEN_LOG) | tail -25

tail:  ## Follow SenseMotherAP log lines live (Ctrl-C to stop)
	@tail -f $(SCREEN_LOG) | grep -a --line-buffered SenseMotherAP

rtl:  ## rtl_433 capture on $(RTL_FREQ) for $(RTL_DUR) s
	@echo "rtl_433 -f $(RTL_FREQ) for $(RTL_DUR)s -> $(RTL_HITS)"
	@rm -f $(RTL_HITS)
	@timeout $(RTL_DUR) rtl_433 -f $(RTL_FREQ) -s 2400000 -g 0 \
		-X 'n=cookie,m=FSK_PCM,s=10,l=10,r=400,preamble=d391' \
		-F "json:$(RTL_HITS)" -M level 2>&1 | tail -3
	@wc -l $(RTL_HITS) 2>/dev/null

parse:  ## Parse the most recent rtl_433 capture
	@python3 $(REPO_ROOT)/scratch/parse_frames.py $(RTL_HITS) 2>&1 | tail -30

sniff: rtl parse  ## rtl_433 capture then decode  (RTL_DUR=<sec> to override)

tx:  ## Fire N test-TX(s) via our sense_ap CLI command (works when app is running)
	@python3 $(REPO_ROOT)/scratch/fire_tx.py $(COUNT) 0.6
	@sleep 2
	@echo "--- last 5 SenseMotherAP test-TX lines ---"
	@grep -a "test-TX" $(SCREEN_LOG) | tail -5

rf-probe:  ## Record 8s of raw IQ at 915 MHz while firing test-TX; report if signal energy is visible above noise
	@python3 $(REPO_ROOT)/scratch/raw_rf_probe.py & probe_pid=$$!; \
		sleep 1; \
		python3 $(REPO_ROOT)/scratch/fire_tx.py 4 1.5; \
		wait $$probe_pid

sniff-tx:  ## rtl_433 for RTL_DUR sec, auto-firing test-TX every 2s via sense_ap CLI, then scan
	@rm -f $(RTL_HITS)
	@timeout $(RTL_DUR) rtl_433 -f $(RTL_FREQ) -s 2400000 \
		-X 'n=cookie,m=FSK_PCM,s=10,l=10,r=400,preamble=d391' \
		-F "json:$(RTL_HITS)" -M level 2>/dev/null & rtl_pid=$$!; \
		sleep 2; \
		bursts=$$(( ($(RTL_DUR) - 2) / 2 )); \
		echo "*** firing $$bursts test-TX bursts during $(RTL_DUR)s rtl_433 window ***"; \
		python3 $(REPO_ROOT)/scratch/fire_tx.py $$bursts 2.0; \
		wait $$rtl_pid 2>/dev/null || true
	@echo "--- ALL rtl_433 hits (long + short) ---"
	@python3 $(REPO_ROOT)/scratch/all_hits.py $(RTL_HITS)
	@echo "--- our AP TX matches ---"
	@python3 $(REPO_ROOT)/scratch/find_our_tx.py $(RTL_HITS)

clean:  ## Remove ufbt build artifacts
	rm -rf dist .vscode
