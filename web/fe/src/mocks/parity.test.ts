// Writes what MSW serves for a fixed list of GET requests to
// web/tests/fixtures/api_parity.json. web/tests/test_api.py sends the same
// requests to the FastAPI app and compares, so the FE's mock layer and the
// backend cannot drift apart without one of the two test suites going red.
//
// After a deliberate change of a response: `npx vitest run -u`, then commit
// the fixture together with the matching backend change.
import { expect, it } from "vitest";

/** "<role> <path>"; role "-" sends no X-Fw-Role header. */
export const PARITY_REQUESTS = [
  "- /recommendations",
  "- /recommendations/rec_round1",
  "- /recommendations/rec_round1/steps",
  "- /recommendations/rec_round1/clusters",
  "- /clusters/clu_1/card",
  "- /clusters/clu_2/card",
  "- /clusters/clu_3/card",
  "- /clusters/clu_4/card",
  "- /repair-tickets?recommendation_id=rec_round1",
  "- /fix-rates",
  "- /evaluations",
  "ADMIN /evaluations",
  "- /evaluations/ev_B_dev",
  "- /evaluations/ev_B_dev/episodes?limit=500",
  "- /evaluations/ev_A_dev/funnel",
  "- /evaluations/ev_B_dev/funnel",
  "- /evaluations/ev_A_dev/failures",
  "- /evaluations/ev_B_dev/failures",
  "- /evaluations/ev_B_dev/system-checks",
  "- /datasets",
  "- /datasets/ds_kbd_teleop",
  "- /datasets/ds_psi_teleop/stages",
  "- /datasets/ds_kbd_teleop/stages",
  "- /datasets/bench_kbd_teleop/stages",
  "- /datasets/ds_egodex/episodes?limit=500",
  "- /datasets/ds_psi_teleop/report",
  "- /datasets/ds_kbd_teleop/report",
  "- /datasets/ds_synth_s1/report",
  "- /datasets/ds_egodex/report",
  "- /intakes",
  "- /results/branches?task_id=two_table",
  "- /results/he-curve",
  "ADMIN /results/he-curve",
  "- /results/e1-curve",
  "- /cost/ledger?limit=500",
  "- /cost/by-branch",
  "- /cost/by-intervention",
  "- /cost/sensitivity",
];

it("records the MSW responses the backend must match", async () => {
  const out: Record<string, unknown> = {};
  for (const request of PARITY_REQUESTS) {
    const [role, path] = request.split(" ") as [string, string];
    const headers: Record<string, string> = role === "-" ? {} : { "X-Fw-Role": role };
    const response = await fetch(`/api${path}`, { headers });
    expect(response.status, request).toBe(200);
    out[request] = await response.json();
  }
  await expect(JSON.stringify(out, null, 1) + "\n").toMatchFileSnapshot(
    "../../../tests/fixtures/api_parity.json",
  );
});
