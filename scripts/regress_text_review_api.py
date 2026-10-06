#!/usr/bin/env python3
"""Exercise the text-review request shape through the real API endpoints."""
from __future__ import annotations

import math
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

QUESTIONS = [
    ("A projectile is fired perpendicular to an inclined plane of angle 30deg "
     "with speed 10 m/s. Find the range on the inclined plane. Take g = 10 m/s^2.", 40 / 3),
    ("A marble rolls down from top of a staircase with constant horizontal velocity 10 m/s. "
     "Each step is 1 m high and 1 m wide. To which step will the marble strike directly? "
     "Take g=9.8 m/s^2.", 21),
    ("A marble rolls down from top of a staircase with constant horizontal velocity 10 m/s. "
     "Each step is 2 m high and 1 m wide. To which step will the marble strike directly? "
     "Take g=9.8 m/s^2.", 41),
]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(tmp) / 'test.sqlite'}"
        from core.main import app
        from core.schema import SolveQuestionRequest

        with TestClient(app) as client:
            for question, expected in QUESTIONS:
                for diagram in [None, {"present": False, "type": "none", "entities": [], "confidence": 0}]:
                    payload = {"question_text_solver": question, "options": [], "givens": [], "diagram": diagram}
                    response = client.post("/solve-question", json=payload)
                    assert response.status_code == 200, response.text
                    data = response.json()
                    assert data["status"] == "passed", data
                    assert math.isclose(data["computed_value"], expected, rel_tol=1e-6), data
                    assert data["walkthrough"] and data["animation_scene_spec"], data
                    if "staircase" in question:
                        quantities = data["animation_scene_spec"]["quantities"]
                        assert quantities["step_width"]["value"] == 1
                        assert quantities["step_height"]["value"] == (2 if expected == 41 else 1)
                        assert quantities["step"]["value"] == expected
                    audit = client.post("/audit/walkthrough-sync", json=payload)
                    assert audit.status_code == 200, audit.text
                    assert audit.json()["solver"]["status"] == "passed", audit.json()

                # An actual but incomplete figure must not silently bypass review.
                payload["diagram"] = {"present": True, "type": "other", "entities": []}
                response = client.post("/solve-question", json=payload)
                assert response.json()["status"] == "needs_review", response.text
                assert response.json()["animation_scene_spec"] is None

            inconsistent = SolveQuestionRequest(
                question_text_solver="Read the figure",
                diagram={"present": False, "type": "incline", "entities": []},
            )
            assert inconsistent.requires_diagram_validation
    print("PASS text-review API: omitted/absent diagrams agree; real diagrams still require validation")


if __name__ == "__main__":
    main()
