"""Hybrid DSP + AI music restoration/mastering (specs/006-audio-engine-masterizacao).

Constitution Princípio XII governs everything here: deterministic DSP
(`dsp.py`) is never replaced by AI; an AI provider's output
(`ai_provider.py`) is never trusted as final without passing back through
`quality.py`'s Quality Guard; `mastering.py`'s `MasteringEngine` is the only
orchestrator, the rest of the app never calls `dsp`/`ai_provider` directly.
"""
