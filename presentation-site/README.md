# Website · Model Engine Core × Data Flywheel

Current presentation: 07/10/2026. A static proposal and evidence reader, with 13 routes. Native GR00T/GR1 A1, human transfer and monetary savings remain unmeasured. The executed MuJoCo reference has idealized state, a scripted sequencer, a learned35×4 predictor and proximity-weld grasp; playback reads saved artifacts.

## Content authority and route ownership

| Role / routes | Source | Renderer |
|---|---|---|
| Pitch and form | `../IDEA.md`, `../deliverables/DENSO-Noi-dung-form-y-tuong.md` | reader / resources |
| overview | `content/overview-flywheel.json` | `dist/overview-flywheel.js/css` |
| product, outcomes, business, roadmap, validation | `content/pitch-pages.json` + engineering/A1 details | `dist/pitch-pages.js/css` |
| Current pilot subtotal | `content/overview-flywheel.json.cost`; shared calculator | overview and business, same inputs |
| learning | engineering architecture and recipe | `dist/learning-core.js/css` |
| engine | `content/model-engine-core.json`, engineering doc17 | `dist/model-engine-core.js/css` |
| sources/research | `content/training-blueprint.json`, `content/research-and-media.json` | `dist/training-blueprint.js/css` |
| architecture | `content/data-flywheel.json`, A1 decision/release/RunPlan contracts | `dist/data-flywheel.js/css` |
| examples | pinned public previews + executed reference | overview-flywheel / engineering renderers |
| Technical architecture | `../idea-v3-2026-10-05/` | expandable dossier |
| Candidate recipe/measurement | `../docs/implementation-plan/skill-a1/` | reader and raw templates |

`dist/engineering.js::renderEngineeringPage` is the route dispatcher. The old route bodies in `app.js` remain historical support code; their presence does not define the current rendered pages. `app.js` owns navigation, full-path Markdown links, media and the reader. The dossier contains current pitch/form, engineering docs, A1 recipes and reference README, followed by canonical/source/history records.

## Build and checks

```bash
python examples/engineering-loop/check.py
python presentation-site/build-content.py
python presentation-site/verify-site.py
node presentation-site/test-presentation.js
node presentation-site/test-improvement.js
bash start-website.sh
```

Reference source/physics/test edits require `check.py` to refresh results, validation receipts and hashes before build. It runs the CPU reference and its tests, not native VLA. `build-content.py` updates canonical snapshots and invokes `build-engineering.py`; it performs no network fetch. Keep the existing static/media assets when copying the project. Normal publishing verifies extracted figure hashes; the optional local source PDF, if present, is also verified. A checkout without `docs/references/papers/` can build.

`verify-site.py` checks generated docs, local media, provenance hashes, source/plan integrity and local Markdown dependency closure inside the primary ZIP. `test-presentation.js` renders all13 route functions with minimal DOM stubs and checks user-level content and full-path document targets; it is not a real browser/responsive/accessibility test. `test-improvement.js` checks outcome/cost accounting in the supporting examples.

Keep the server terminal open while viewing [the local website](http://127.0.0.1:4175/#overview). If it is already running, open the link directly. Use Ctrl+C in that terminal to stop it.

## Packages and source images

`assets/idea-v3.1.zip` ships the current dossier, IDEA/form, A1 recipes/templates and reference code/results at original relative paths, with local Markdown dependencies included. `assets/skill-a1-plan.zip` remains an optional smaller A1-only package. Template null values mean not measured; they are not native receipts.

Create an extra handover ZIP only when needed:

```bash
python presentation-site/package.py --kind website
# Or: working dossier including the website, without a nested website ZIP
python presentation-site/package.py --kind dossier
```

Exports go to `deliverables/`. The default creates only the website package; `--kind all` explicitly creates both. Source papers and build caches are excluded. Normal builds need neither export; they can be deleted and recreated later.

Prioritize original paper/author architecture figures, with attribution and scope. FluxVLA Figures1–5 are pinned extracted assets with source hashes and CC BY4.0 credit, shipped offline. The original GR00T N1.5 architecture SVG loads from NVIDIA and needs internet; the source link remains visible if the image cannot load. Custom flywheel/A1 diagrams are labelled proposals, separate from original figures. Upstream benchmarks are not project results.

Planning is8–12weeks after resource/task feasibility; H/action-free/workflow studies and real hardware have separate gates and caps. The current form and PowerPoint are synchronized as of07/10/2026. The editable deck contains21slides and is below15MB. Team names, member capabilities and task ownership still need completion before submission. This site is ready for local review, not a claim of production or factory acceptance.
