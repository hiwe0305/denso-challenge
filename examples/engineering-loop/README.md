# Executable engineering reference · v3.1

Run a real data/training/MuJoCo/evidence/promotion pipeline. This is NOT FluxVLA/GR00T/GR1, a VLM, human-motion transfer, a contact-accurate gripper or a monetary-savings experiment.

## Run from repository root

```bash
python examples/engineering-loop/run.py
python -m pytest -q examples/engineering-loop/test_pipeline.py
```

Portable copy: `python example/run.py --out example/results`; `python -m pytest -q example/test_pipeline.py`.

Python 3.11+; NumPy, MuJoCo and pytest (see requirements.txt). CPU. No remote assets or model downloads. Each rerun writes its results and artifact/source hashes. Reference action4D xyz/grip; measured simulator state is declared idealized input. Sequencer scripted, predictor weights fit by ridge behavior cloning. Grasp proximity/weld, not a calibrated physical gripper. Task target is fixed instruction binding, not learned language understanding.

R: one executed seed. S: same seed plus object/target transforms actually executed in MuJoCo. C: same seed plus expert-reset correction on development; alternative to S, not automatic extra training. Dataset replay preserved. Final constructed only after recipes/checkpoints freeze and never used for training. Independent recording count differs from seed ancestor count.

Actual run: S12/12 final; C passes development but0/12 final so promotion rejected. This demonstrates reference engineering gates, not native VLA effectiveness. Binding-fault, unknown-verifier and zero-skill cases have recorded executions. Tests reject invalid/contaminated data and incorrect promotion. Human source remains not_integrated.

## Artifacts

`results/report.json`: scope, observations, source counts, train receipts, final/regression/negative outcomes and gates. `manifest.json`: source/world/artifact hashes. `*.checkpoint.json`: actual trained weights. `before.json`, `after-synthetic.json`, `after-correction.json`: step-by-step predicted/sent/measured states and scores. Releases contain exact training rows/profile/provenance/root/scenario IDs. `world.xml`: simulator model.

Website is a replay of those recordings. It does not train a model in the browser. Run the commands above to reproduce physics and training.
