# Cafe TFC & Restro Review Flow

## Goal

Give Cafe TFC & Restro customers a simple way to turn their own short visit notes and selected rating into editable review drafts, then copy one draft and open one chosen review platform.

## Customer experience

1. Show the existing TFC logo from `465615789_848662040684569_2552862254939855198_n.jpg`, the business name `Cafe TFC & Restro`, and tagline `Food · Coffee · Good Vibes`.
2. Ask for a short description of what stood out during the visit.
3. Let the customer choose a rating from one to five stars.
4. On generation, request exactly 30 short review drafts for the chosen rating. Drafts should be varied in wording and emphasis while using only facts from the customer's notes. The model must not invent menu items, staff names, service events, amenities, or other visit details.
5. Show the 30 drafts in a horizontal swipeable row consistent with the current compact, single-column design. Indicate the selected draft position out of 30. Tapping a card loads it into an editable text area.
6. `Copy & Submit` copies the selected, edited text and reveals the available destinations: Google, Justdial, and Instagram.
7. Choosing one destination opens its configured external URL and locks the other destinations for this review. Starting a new review clears the note, rating, drafts, and platform lock so the customer can choose again.
8. The customer completes the final paste and submission on the external platform. The app does not claim to post reviews automatically.

## Business configuration

- Name: `Cafe TFC & Restro`
- Type: `Cafe & Restaurant`
- Location: `Rajpur, Barwani, MP`
- Tagline: `Food · Coffee · Good Vibes`
- Logo: existing JPEG in the project root
- Google and Justdial destinations: retain the URLs currently configured in `index.html`
- Instagram destination: `https://www.instagram.com/cafe_tfc_and_restro/`

## Frontend and API responsibilities

The single-page `index.html` keeps the compact visual style shown in the supplied reference. It owns the experience note, star selection, loading/error feedback, horizontal card selection, draft editing, copy feedback, and per-review platform selection/lock.

The FastAPI `POST /generate-reviews` request gains a customer experience note and accepts a count up to 30. The UI always requests 30. The response retains the existing `reviews`, `rating`, and `language` fields. The generator makes one model request per generation and validates that it received a non-empty list with the requested number of strings; invalid or incomplete model output returns a clear API error rather than a successful-looking partial result.

The prompt must match the chosen rating and avoid adding facts not present in the customer note. Drafts should remain short for browsing and should express only the sentiment supported by the rating and customer-provided details.

## Error behavior

- Empty experience notes and missing ratings cannot be submitted for generation.
- Loading state prevents duplicate generation submissions.
- API/provider failures are shown to the customer as a readable error; technical details remain in backend logs.
- Clipboard failure is surfaced rather than silently claiming the review was copied.
- A platform cannot be chosen before a draft is copied, and only one can be chosen for a review.

## Verification

- API tests cover request validation, notes/rating/count propagation, exact 30-item response handling, and invalid/incomplete model output.
- Frontend behavior is verified for horizontal draft selection, edited-text copy, platform locking, and reset/unlock on a new review.
- Live integration verification checks `/health` and a real `/generate-reviews` request using supplied notes for ratings 1 through 5 where API quota allows.
- Manual browser verification checks the compact layout, TFC logo, horizontal swipe behavior, visible errors, platform destinations, and the new-review reset.
