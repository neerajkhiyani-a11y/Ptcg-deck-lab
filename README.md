# ptcg-deck-lab

Tests Pokémon TCG decks against the current meta by simulating thousands of games on
`cabt`, The Pokémon Company's official battle engine (shipped in `kaggle-environments` for
the 2026 Pokémon TCG AI Battle Challenge). Notes and status live on the CNS Deck Lab page.

## Layout
- `lab/cards.py`: engine card DB, decklist → engine IDs (name aliases, stand-ins for cards the engine lacks)
- `lab/agents.py`: deck-agnostic heuristic bot (`heuristic`) and `random`
- `lab/search.py`: ctypes bindings for the engine's built-in search. The signatures are reverse-engineered from `libcg.so`, so recheck them if the package updates.
- `lab/lookahead.py`: search bot (`lookahead:N`). For each main-phase option it runs N sampled hidden-information rollouts through the opponent's reply, then scores the board.
- `lab/harness.py`: N games with alternating seats over multiple processes, reporting win rate and 95% CI
- `lab/data/meta_lists.json`: top lists keyed by Limitless decklist ID (Louisville Regional, Oct 10 2026, plus Worlds Crustle)
- `tools/`: scraping and coverage-check helpers (expect raw pages in `dl/` and `dlc/`, which are git-ignored)

## Usage
```
pip install -r requirements.txt
python3 run.py 28756 29678 lookahead:2 lookahead:2 100   # Crustle vs Dragapult
```

## Calibration (Oct 15, 2026)
| Matchup | Sim | Real (Turin) |
|---|---|---|
| Crustle vs Dragapult | 62–75% | 69% |
| Crustle vs Festival Lead | 67% | 22% (bot misplays Festival Lead) |
