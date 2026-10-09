# Mobile Font Readability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the review flow easier to read on mobile by modestly increasing its small text while preserving its existing compact layout.

**Architecture:** Keep the existing single-page HTML and styling. Add mobile-only font-size overrides for the text-heavy controls and supporting copy; leave star sizes, desktop typography, and layout structure unchanged.

**Tech Stack:** HTML, CSS, browser viewport validation.

---

## Files and responsibilities

- Modify `index.html`: add a mobile media query after the existing component styles to increase small copy, card text, controls, and business name typography.
- No runtime logic or dependencies change.

### Task 1: Increase small text sizes on mobile

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add mobile-only font-size overrides**

Append this rule block to the existing `<style>` contents, before `</style>`:

```css
    @media (max-width: 480px) {
      .biz-name { font-size: 18px; }
      .brand-tag,
      .experience-hint,
      .star-hint,
      .draft-count,
      .card-tap,
      .platform-sub,
      .new-review-btn { font-size: 12px; }
      .experience-label,
      .experience-textarea,
      .draft-title,
      .review-card,
      .review-textarea,
      .platform-btn { font-size: 14px; }
      .submit-btn,
      .platform-title,
      .error-msg { font-size: 15px; }
      .thinking-text { font-size: 15px; }
    }
```

- [ ] **Step 2: Validate the page at a mobile viewport**

Open `index.html` in the browser, set the viewport to 390×844, and confirm the heading, experience field, review cards, submit button, and platform options render with larger text and no horizontal page overflow.

- [ ] **Step 3: Confirm desktop styles are unchanged**

Set the browser viewport to 1280×800 and confirm the mobile media query is inactive and the existing typography/layout remain as before.
