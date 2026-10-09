# Cafe TFC & Restro Review Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the Cafe TFC & Restro page so a customer's short note and selected rating generate 30 truthful, editable review drafts that can be copied and sent to one chosen platform.

**Architecture:** Keep the existing single-page HTML/CSS/JavaScript frontend and FastAPI backend. Extend the existing generation request with the customer's experience note and a 30-draft limit; keep platform and draft selection state in the page, opening the chosen external platform only after a user click.

**Tech Stack:** HTML, CSS, browser JavaScript, FastAPI, Pydantic v2, Groq SDK, Python `unittest` and FastAPI `TestClient`.

---

## Files and responsibilities

- Modify `main.py`: validate the experience note and requested count; prompt the model to generate 30 short, varied, rating-consistent drafts using only supplied facts; reject incomplete or malformed model output with an explicit upstream error.
- Modify `index.html`: use the existing TFC logo and approved business/platform configuration; implement the note → stars → horizontal draft cards → editable copy → one-platform lock → new-review reset flow with the screenshot's minimal styling.
- Modify `tests/test_generation_model.py`: add regression coverage for the new API input, exact count, prompt grounding, invalid requests, and provider output validation.
- No new runtime dependencies or frontend framework. The workspace currently is not a Git repository, so do not run `git commit`; commit-sized changes can be made if version control is initialized later.

## Task 1: Generate 30 grounded drafts through the existing API

**Files:**
- Modify: `main.py`
- Test: `tests/test_generation_model.py`

- [ ] **Step 1: Add a failing test for experience-note and count propagation**

In `ReviewGenerationModelTests`, import `json` and replace the one-item fake completion content with a JSON array of 30 strings. Capture the passed Groq options and prompt as follows:

```python
reviews = [f"Draft {i}" for i in range(30)]
captured = {}

def create_completion(**kwargs):
    captured.update(kwargs)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(reviews)))]
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
            "business_name": "Cafe TFC & Restro",
            "location": "Rajpur, Barwani, MP",
            "business_type": "Cafe & Restaurant",
            "experience": "Friendly staff and paneer tikka were good",
            "rating": 3,
            "count": 30,
        },
    )

assert response.status_code == 200
assert len(response.json()["reviews"]) == 30
user_prompt = next(message["content"] for message in captured["messages"] if message["role"] == "user")
assert "Friendly staff and paneer tikka were good" in user_prompt
assert "exactly 30" in user_prompt
assert "Do not invent" in user_prompt
assert captured["model"] == "openai/gpt-oss-120b"
assert captured["max_tokens"] == 4096
```

- [ ] **Step 2: Run the regression test and confirm it fails on the current API**

Run from the project root:

```powershell
& "C:\Users\Chetan Prajapat\AppData\Local\Python\pythoncore-3.12-64\python.exe" -m unittest discover -s tests -p test_generation_model.py -v
```

Expected: FAIL because the current `ReviewRequest` has no `experience` field and permits counts only up to 5.

- [ ] **Step 3: Add a failing test for incomplete model output**

Use the request body with `business_name`, `location`, `business_type`, `experience: "Food was good"`, `rating: 3`, and `count: 3`; patch the fake Groq client to return only two JSON strings, and assert that `/generate-reviews` returns HTTP 502 with `detail` equal to `Review generation failed. Please try again.` The current endpoint incorrectly returns a non-empty partial list as success.

- [ ] **Step 4: Run the incomplete-output test and confirm it fails**

```powershell
& "C:\Users\Chetan Prajapat\AppData\Local\Python\pythoncore-3.12-64\python.exe" -m unittest discover -s tests -p test_generation_model.py -v
```

Expected: the incomplete-output case fails because the current endpoint returns HTTP 200 with two reviews.

- [ ] **Step 5: Add failing request-validation tests**

Add three focused `TestClient` cases using a valid common request body:

```python
valid_request = {
    "business_name": "Cafe TFC & Restro",
    "location": "Rajpur, Barwani, MP",
    "business_type": "Cafe & Restaurant",
    "experience": "Food was good",
    "rating": 3,
    "count": 30,
}

api = TestClient(main.app)
assert api.post("/generate-reviews", json={**valid_request, "count": 31}).status_code == 422
assert api.post("/generate-reviews", json={**valid_request, "experience": "   "}).status_code == 422
assert api.post("/generate-reviews", json={k: v for k, v in valid_request.items() if k != "experience"}).status_code == 422
```

- [ ] **Step 6: Run the request-validation tests and confirm they fail for the expected behavior**

Run:

```powershell
& "C:\Users\Chetan Prajapat\AppData\Local\Python\pythoncore-3.12-64\python.exe" -m unittest discover -s tests -p test_generation_model.py -v
```

Expected: the new tests fail because the current request model neither accepts the experience note nor enforces the new 30-draft contract.

- [ ] **Step 7: Define and validate the request fields**

In `main.py`, import `field_validator` from Pydantic and define these fields in `ReviewRequest`, keeping the other business fields and existing rating constraint:

```python
experience: str = Field(..., min_length=1, max_length=500)
count: int = Field(default=30, ge=1, le=30)

@field_validator("experience")
@classmethod
def strip_experience(cls, value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Experience note cannot be blank")
    return value
```

- [ ] **Step 8: Ground the generation prompt and allow enough output**

In `build_prompt`, place `req.experience` in a clearly marked customer-provided section. Keep the rating-specific guidance and add these explicit generation constraints:

```text
Customer's actual visit notes:
{req.experience}

Write exactly {req.count} different, concise first-person review drafts for this {req.rating}-star rating.
Use only facts explicitly present in the customer's notes. Do not invent dishes, staff names,
service events, amenities, prices, or other visit details. Keep sentiment consistent with the rating.
Vary wording and emphasis without adding unsupported facts. Respond only with a JSON array of strings.
```

Set the existing model call's `max_tokens` to `4096`; preserve `openai/gpt-oss-120b` and current SDK conventions.

- [ ] **Step 9: Validate the provider response before returning it**

After JSON parsing, reject a non-list, a list whose size differs from `req.count`, or any non-string/blank entry. Do not slice the response to make incomplete output look successful. Use `logging.getLogger(__name__)`; return a customer-safe 502 while retaining the traceback in server logs:

```python
if (
    not isinstance(reviews, list)
    or len(reviews) != req.count
    or any(not isinstance(item, str) or not item.strip() for item in reviews)
):
    raise ValueError("Model returned an invalid review list")

return ReviewResponse(reviews=[item.strip() for item in reviews], rating=req.rating, language=req.language)
```

Catch JSON/value validation and provider errors at the endpoint boundary, log with `logger.exception(...)`, and raise `HTTPException(status_code=502, detail="Review generation failed. Please try again.")` from the caught exception. Keep missing API-key configuration as an explicit configuration error before calling Groq.

- [ ] **Step 10: Run backend tests**

Run:

```powershell
& "C:\Users\Chetan Prajapat\AppData\Local\Python\pythoncore-3.12-64\python.exe" -m unittest discover -s tests -p test_generation_model.py -v
```

Expected: all request, prompt, and provider-response tests pass.

## Task 2: Implement the minimal TFC customer page and one-platform flow

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Update business identity and destinations**

Set the visible name to `Cafe TFC & Restro`, type to `Cafe & Restaurant`, and tagline to `Food · Coffee · Good Vibes`. Display the existing root JPEG as the TFC logo. Keep the current Google and Justdial destinations; set Instagram to `https://www.instagram.com/cafe_tfc_and_restro/`. Remove Zomato and Swiggy from the displayed platform configuration.

Use the relative image URL `465615789_848662040684569_2552862254939855198_n.jpg` so the existing local frontend server can serve the root-level asset. Keep the existing Google and Justdial URL values verbatim.

- [ ] **Step 2: Add the customer experience note to the compact form**

Add a labelled, required experience textarea before the existing star rating. Keep the current single-column visual style and avoid adding unrelated sections or settings. Do not call the API until a non-empty note and a 1–5 rating are available.

Use a stable element id `experienceText`, a visible label `What stood out during your visit?`, and `maxlength="500"`. Keep the existing star click behavior as the trigger: if the note is blank, focus the textarea and show a concise inline error instead of sending a request.

- [ ] **Step 3: Request 30 drafts for the selected rating**

Update the generation payload to send `business_name`, `location`, `business_type`, `experience`, `rating`, and `count: 30`. Keep one request per rating selection. Disable star selection while the request is pending and restore it on both success and failure. Show the returned API error detail in the existing error area without leaving the thinking indicator visible.

The request body must have this shape:

```javascript
{
  business_name: BUSINESS.name,
  location: BUSINESS.location,
  business_type: BUSINESS.type,
  experience: experienceText.value.trim(),
  rating,
  count: 30
}
```

- [ ] **Step 4: Render the 30 drafts as horizontal cards**

Render cards from the validated `reviews` array in the existing horizontally scrollable container. Show the current selected position as `n / 30`. Make card text safe by rendering review text as text content, not interpolated HTML. Selecting a card highlights it and copies its content into the existing editable textarea.

Track `selectedReviewIndex` (initially `-1`). For each array item, create a button/card, assign review copy through `textContent`, and on click set `selectedReviewIndex`, put the review in `reviewText.value`, toggle the selected class, and update an `n / 30` position label. Do not place model text into `innerHTML`.

- [ ] **Step 5: Implement guarded copy and platform selection**

Keep the `Copy & Submit` button disabled until a draft is selected and the edited text is non-empty. Make `copy(text)` return a boolean: try `navigator.clipboard.writeText(text)`, then a temporary textarea plus `document.execCommand("copy")`; return `false` if neither succeeds. `handleSubmit` must await copy and reveal the platform sheet only on success. When one platform is chosen, open its configured URL synchronously within that click, visually mark the chosen platform, and disable all destination buttons until a new review starts.

- [ ] **Step 6: Add the new-review reset**

After a platform has been selected, show a concise `New review` action. It clears the note, rating, cards, selected draft, textarea, errors, and selected platform; hides the results and platform sheet; restores star/platform controls; and returns focus to the experience note.

Implement this as one `startNewReview()` handler so each state field is reset together; do not reload the page. The platform lock is scoped to this review only.

- [ ] **Step 7: Check HTML and browser interaction**

Open `index.html` using the existing local frontend server and verify:

1. The logo, name, and tagline match the approved screenshot.
2. A blank note cannot generate; a note plus each rating from 1 to 5 triggers generation.
3. The 30 cards can be swiped horizontally; choosing a card updates the editor and `n / 30` indicator.
4. Editing text changes the copied text.
5. Copy reveals exactly Google, Justdial, and Instagram.
6. Choosing one destination opens the matching URL and disables the others.
7. `New review` resets the state and allows a different platform choice.
8. API and clipboard failures are shown to the user, and loading state ends.

## Task 3: Verify end-to-end API output

**Files:**
- No additional files.

- [ ] **Step 1: Run all backend unit tests**

```powershell
& "C:\Users\Chetan Prajapat\AppData\Local\Python\pythoncore-3.12-64\python.exe" -m unittest discover -s tests -v
```

Expected: all tests pass with no failures.

- [ ] **Step 2: Verify service health**

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing | Select-Object -ExpandProperty Content
```

Expected body: `{"status":"ok"}`.

- [ ] **Step 3: Verify live generation returns exactly 30 drafts**

Run:

```powershell
$body = @{
    business_name = "Cafe TFC & Restro"
    location = "Rajpur, Barwani, MP"
    business_type = "Cafe & Restaurant"
    experience = "Friendly staff and paneer tikka were good"
    rating = 3
    count = 30
} | ConvertTo-Json
$response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/generate-reviews" -Method Post -ContentType "application/json" -Body $body
if ($response.reviews.Count -ne 30) { throw "Expected 30 reviews; got $($response.reviews.Count)" }
$response | ConvertTo-Json -Depth 4
```

Expected: HTTP 200 with exactly 30 non-empty string drafts, `rating` 3, and `language` returned. Inspect several drafts to confirm they do not mention unprovided foods, staff names, or events.

- [ ] **Step 4: Verify all rating bands**

Run the same request once for each remaining rating and fail the check if any response does not contain 30 items:

```powershell
foreach ($rating in 1, 2, 4, 5) {
    $body = @{
        business_name = "Cafe TFC & Restro"
        location = "Rajpur, Barwani, MP"
        business_type = "Cafe & Restaurant"
        experience = "Friendly staff and paneer tikka were good"
        rating = $rating
        count = 30
    } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/generate-reviews" -Method Post -ContentType "application/json" -Body $body
    if ($response.reviews.Count -ne 30) { throw "Rating $rating returned $($response.reviews.Count) reviews" }
    Write-Output "Rating $rating returned 30 drafts"
}
```

Confirm each response's tone follows its requested rating without inventing visit details. If provider limits prevent a live call, record the exact upstream error and retain the passing mocked API tests as the local verification evidence.
