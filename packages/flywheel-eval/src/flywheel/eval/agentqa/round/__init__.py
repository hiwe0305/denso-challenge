"""The round pipeline of Agent QA/QC (DA-43, architecture 20/11/2026).

Eight fixed steps, each a function from files to files in one run directory:
pack (B0), admit (B1), measure (B2), hypothesize (B3), judge (B4, the only step
that calls a model), verify (B5), assemble (B6), render (B7).
"""
