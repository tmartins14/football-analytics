# =============================================================================
# pieces/01-world-cup-48/Makefile
# Run from the piece root: cd pieces/01-world-cup-48
# =============================================================================
 
PYTHON = python
SCRIPTS = scripts
 
.PHONY: normalize elo cis
 
normalize:
	$(PYTHON) $(SCRIPTS)/normalize_team_names.py
 
elo:
	$(PYTHON) $(SCRIPTS)/calculate_elo.py
 
cis:
	$(PYTHON) $(SCRIPTS)/calculate_cis.py

group-standings:
	$(PYTHON) $(SCRIPTS)/derive_group_standings.py