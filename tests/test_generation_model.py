import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import main


class ReviewGenerationModelTests(unittest.TestCase):
    def test_generates_thirty_reviews_using_only_customer_notes(self):
        reviews = [f"Draft {index}" for index in range(30)]
        captured = {}

        def create_completion(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=json.dumps(reviews))
                    )
                ]
            )

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create_completion)
            )
        )

        with patch.object(main, "client", fake_client):
            response = TestClient(main.app).post(
                "/generate-reviews",
                json={
                    "business_name": "The Traffic Cafe",
                    "location": "Rajpur, Barwani, MP",
                    "business_type": "Cafe & Restaurant",
                    "experience": "Friendly staff and paneer tikka were good",
                    "rating": 3,
                    "count": 30,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["reviews"]), 30)
        user_prompt = next(
            message["content"]
            for message in captured["messages"]
            if message["role"] == "user"
        )
        self.assertIn("Friendly staff and paneer tikka were good", user_prompt)
        self.assertIn("exactly 30", user_prompt)
        self.assertIn("Do not invent", user_prompt)
        self.assertEqual(captured["model"], "openai/gpt-oss-120b")
        self.assertEqual(captured["max_tokens"], 4096)

    def test_rejects_incomplete_model_review_list(self):
        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(
                                    content='["First review", "Second review"]'
                                )
                            )
                        ]
                    )
                )
            )
        )

        with patch.object(main, "client", fake_client):
            response = TestClient(main.app).post(
                "/generate-reviews",
                json={
                    "business_name": "Cafe TFC & Restro",
                    "location": "Rajpur, Barwani, MP",
                    "business_type": "Cafe & Restaurant",
                    "experience": "Food was good",
                    "rating": 3,
                    "count": 3,
                },
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "Review generation failed. Please try again.",
        )

    def test_rejects_blank_or_missing_experience_and_counts_over_thirty(self):
        calls = []

        def create_completion(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps(["One", "Two", "Three"])
                        )
                    )
                ]
            )

        fake_client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=create_completion)
            )
        )
        api = TestClient(main.app)
        valid_request = {
            "business_name": "Cafe TFC & Restro",
            "location": "Rajpur, Barwani, MP",
            "business_type": "Cafe & Restaurant",
            "experience": "Food was good",
            "rating": 3,
            "count": 3,
        }

        with patch.object(main, "client", fake_client):
            too_many = api.post(
                "/generate-reviews",
                json={**valid_request, "count": 31},
            )
            blank_experience = api.post(
                "/generate-reviews",
                json={**valid_request, "experience": "   "},
            )
            missing_experience = api.post(
                "/generate-reviews",
                json={
                    key: value
                    for key, value in valid_request.items()
                    if key != "experience"
                },
            )

        self.assertEqual(too_many.status_code, 422)
        self.assertEqual(too_many.json()["detail"][0]["ctx"]["le"], 30)
        self.assertEqual(blank_experience.status_code, 422)
        self.assertEqual(missing_experience.status_code, 422)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
