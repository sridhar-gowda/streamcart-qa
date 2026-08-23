# QA Architect Assessment — Multi-Platform Test Framework Design

## Overview

This is a take-home assessment for the **QA Architect** role. You will design
and build a **multi-platform test automation framework from scratch**, then
prove it works with a passing test suite against
[SauceDemo](https://www.saucedemo.com/).

Unlike a typical SDET assignment where you follow established patterns, this
assessment asks you to **create** the patterns. You decide the architecture,
the abstractions, and the conventions that a team of SDETs would follow.

| Detail              | Value                                          |
|---------------------|------------------------------------------------|
| **Time limit**      | 2–3 days (estimated 12–17 hours of active work)|
| **Language**        | Python 3.10+                                   |
| **Test runner**     | pytest (required)                              |
| **Target app**      | https://www.saucedemo.com/                     |
| **Deliverables**    | Code + Architecture Decision Record + Video    |

---

## The Scenario

You are the QA Architect for **StreamCart** — a multi-platform e-commerce
product. Read [`SCENARIO.md`](SCENARIO.md) for the full product description.

**In short:** StreamCart runs on Web, iOS, Android, Fire TV, Roku, and
Apple TV. All platforms share the same core user journey (browse, add to cart,
checkout), but each has a fundamentally different interaction model.

Your framework must support testing **all platforms** through a unified
architecture. For this assessment, you will implement working tests only for
the **Web platform** (using SauceDemo as a stand-in), while designing the
abstraction layer to accommodate mobile and TV platforms.

---

## Setup

You start with an **empty project**. There is no provided framework, no base
classes, no page objects. You build everything.

```bash
# 1. Create a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 2. Install your chosen dependencies
# (see requirements-baseline.txt for the only hard constraint: Python 3.10+ and pytest)
pip install -r requirements.txt  # You create this file

# 3. Verify your framework works
pytest -v
```

> **Constraint:** You must use **pytest** as the test runner. All other library
> choices (Selenium, Playwright, BDD framework, assertion library, etc.) are
> yours to make — and justify in your ADR.

---

## Your Tasks

### Task 1: Framework Architecture & Project Structure
**Estimated time:** 3–4 hours | **Priority:** MUST

Design and build the core framework from scratch:

- **Project structure** — organize your code into clear, logical layers
- **Driver abstraction** — an interface or protocol that defines what a
  "platform driver" can do (navigate, find elements, interact, wait), without
  coupling to any specific library
- **Configuration system** — externalized settings for environments, platforms,
  credentials, and execution options (no hardcoded values in test code)
- **Utility layer** — logging, assertion helpers, screenshot/artifact capture,
  reporting hooks
- **Fixture architecture** — pytest fixtures for driver lifecycle management,
  page object instantiation, and test data

**What we evaluate:**
- Clean separation of concerns across layers
- Interface/Protocol design quality
- How intuitive the project structure is for a new team member

---

### Task 2: Multi-Platform Abstraction Layer
**Estimated time:** 2–3 hours | **Priority:** MUST

Design the abstraction that makes your framework platform-agnostic:

- **Platform driver interface** — an abstract definition (Protocol, ABC, or
  equivalent) of what every platform driver must implement
- **Web driver adapter** — a concrete implementation wrapping your chosen web
  automation library (e.g., Selenium). This must be fully functional.
- **Stub implementations** — skeleton drivers for at least **2 additional
  platforms** (e.g., Mobile via Appium, Fire TV, Roku). These don't need to
  execute — they demonstrate how the abstraction extends.
- **Platform-aware Page Object base** — a base class that page objects inherit
  from, which interacts with the driver abstraction (not the raw library)
- **Platform-specific handling** — an explicit mechanism for capabilities that
  differ across platforms (hover, swipe, d-pad navigation, etc.)

**What we evaluate:**
- Whether Selenium/library-specific types leak into the page or test layers
- Quality of stub implementations (correct signatures, meaningful docstrings —
  not empty files)
- Whether adding a new platform requires **new files only** (no modifying
  existing framework code)

---

### Task 3: Working Test Suite — SauceDemo
**Estimated time:** 3–4 hours | **Priority:** MUST

Prove your framework works with a real, passing test suite:

- **Page objects** for at minimum: Login, Inventory, Cart, and Checkout
- **At least 14 test scenarios** covering:
  - Login — valid credentials, invalid credentials, locked-out user
  - Inventory — products displayed, sorting (name A-Z, Z-A, price low-high,
    high-low), add to cart, remove from cart
  - Cart — items displayed with correct details, remove item, continue
    shopping, proceed to checkout
  - Checkout — form validation (missing fields), order summary, successful
    completion
- Tests must exercise **your framework's patterns** (not bypass them)
- Your choice of test organization: BDD (pytest-bdd, Behave), data-driven,
  keyword-driven, or plain pytest — justify your choice in the ADR

**What we evaluate:**
- All tests pass with `pytest -v`
- Page objects follow the patterns YOU established (not ad-hoc shortcuts)
- Test readability — someone unfamiliar with SauceDemo can understand what's
  being tested
- No anti-patterns: `time.sleep()`, hardcoded waits, global state, assertions
  in page objects

---

### Task 4: CI/CD Pipeline Design
**Estimated time:** 1–2 hours | **Priority:** SHOULD

Design a CI/CD pipeline for your framework:

- **Working CI configuration** — a GitHub Actions `.yml`, GitLab CI
  `.gitlab-ci.yml`, or equivalent that:
  - Installs dependencies
  - Runs the web tests in headless mode
  - Generates and uploads a test report
  - Captures artifacts (screenshots, logs) on failure
- **Pipeline strategy document** — a section in your ADR or a separate
  `PIPELINE.md` covering:
  - How the pipeline extends to mobile and TV test execution
  - Parallelization strategy across platforms and test suites
  - Environment management (dev, staging, production)
  - When tests run (PR gates, nightly regression, deploy triggers)
  - Failure notification and reporting

**What we evaluate:**
- CI file is syntactically valid and realistic
- Multi-platform execution is addressed concretely (not just "we could
  parallelize")
- Practical trade-offs considered (cost, speed, resource management)

---

### Task 5: Architecture Decision Record (ADR)
**Estimated time:** 2–3 hours | **Priority:** MUST

Document your architectural decisions in an `ADR.md` file:

1. **Framework & library selection** — Why these libraries? What alternatives
   did you evaluate and reject?
2. **Architecture overview** — Layer diagram showing component relationships
   and data flow
3. **Platform abstraction strategy** — Why this pattern? How does it handle
   the differences between web clicks, mobile taps, and TV remote navigation?
4. **Page Object design** — What pattern did you choose (classic POM,
   Screenplay, component-based, hybrid)? Why? How does it scale?
5. **Test data management** — How is test data provided, isolated, and managed
   across runs and platforms?
6. **Team scaling** — How does this framework support 10 SDETs writing tests
   daily? 50 SDETs? What conventions and guardrails would you enforce?
7. **Trade-offs & limitations** — What was sacrificed for the timeline? What
   would you build differently with 2 more weeks?

**What we evaluate:**
- Each decision includes context, alternatives considered, and rationale
  (not just "I used X")
- Honest self-assessment of limitations
- Awareness of team dynamics (onboarding, code review, merge conflicts)
- Writing quality — concise, structured, technical but accessible

---

### Task 6: Video Walkthrough
**Estimated time:** 1–1.5 hours (recording + prep) | **Priority:** MUST

Record a **10–15 minute** video walkthrough:

1. **Tests running** — show `pytest -v` output, all tests passing
2. **Architecture walkthrough** — navigate your codebase and explain the layer
   structure, key abstractions, and why you organized things this way
3. **"Add a platform" demo** — show concretely what files a developer would
   create to add support for a new platform (e.g., Roku). Walk through the
   interface they'd implement.
4. **"Onboard an SDET" pitch** — explain how a new SDET would write their
   first test using your framework
5. **One thing you'd change** — if you could start over, what would you do
   differently?

Upload to Google Drive, Loom, or YouTube (unlisted).

---

## Bonus Opportunities (+15 points max)

These are not required but demonstrate additional depth:

| Bonus | Points | Description |
|-------|--------|-------------|
| BDD integration | +3 | pytest-bdd or Behave with well-written Gherkin feature files |
| Screenplay pattern | +3 | Actor/Task/Question pattern alongside or instead of POM |
| Docker support | +2 | Dockerfile and/or docker-compose that runs tests in a container |
| Parallel execution | +2 | pytest-xdist or similar with proper test isolation |
| Custom pytest plugin | +2 | Custom plugin for reporting, platform selection, or categorization |
| Linting & quality gates | +1 | ruff/flake8/mypy config, pre-commit hooks |
| Composable page components | +2 | Shared components (header, nav, cart badge) as reusable objects |

---

## SauceDemo Reference

### Test Users

| Username | Behavior |
|----------|----------|
| `standard_user` | Normal user — use this for most tests |
| `locked_out_user` | Cannot log in — receives error message |
| `problem_user` | UI has intentional bugs |
| `performance_glitch_user` | Slow responses |
| `error_user` | Random errors during flows |
| `visual_user` | Visual differences in UI |

**Password for all users:** `secret_sauce`

### Application Pages

| Page | URL Path | Key Elements |
|------|----------|-------------|
| Login | `/` | Username, password, login button, error messages |
| Inventory | `/inventory.html` | Product list, sort dropdown, add/remove cart buttons, cart badge |
| Cart | `/cart.html` | Cart items, remove buttons, continue shopping, checkout |
| Checkout Step One | `/checkout-step-one.html` | First name, last name, zip code, cancel, continue |
| Checkout Step Two | `/checkout-step-two.html` | Order summary, item total, tax, total, finish |
| Checkout Complete | `/checkout-complete.html` | Confirmation message, back to products |

> **Tip:** SauceDemo uses `data-test` attributes on most interactive elements.
> Use your browser's DevTools to inspect elements and find reliable locators.

---

## Time Management

| Task | Estimated | Priority |
|------|-----------|----------|
| Task 1: Framework Architecture | 3–4 hours | MUST |
| Task 2: Platform Abstraction | 2–3 hours | MUST |
| Task 3: Working Tests | 3–4 hours | MUST |
| Task 4: CI/CD Design | 1–2 hours | SHOULD |
| Task 5: ADR | 2–3 hours | MUST |
| Task 6: Video | 1–1.5 hours | MUST |
| **Total** | **12–17 hours** | |

> **Important:** We value a **complete, working, well-documented solution**
> over a perfect one. If you are running short on time, prioritize:
> 1. Working tests against SauceDemo (proves the framework works)
> 2. The platform abstraction design (proves you think like an architect)
> 3. The ADR (proves you can communicate decisions)
>
> A framework that works and is well-explained will score higher than one that
> is over-engineered but incomplete or unexplained.

---

## Evaluation Criteria

Your submission is evaluated across five dimensions:

| Category | Weight | What We Look For |
|----------|--------|-----------------|
| **Framework Architecture** | 30% | Layer separation, abstract driver interface, factory/DI patterns, configuration management, project structure clarity |
| **Platform Extensibility** | 20% | Driver interface quality, Selenium containment, stub quality, open-closed principle, platform-specific handling |
| **Working Code** | 25% | All tests pass, sufficient coverage, page objects follow own patterns, no anti-patterns |
| **Strategic Thinking** | 15% | ADR quality, trade-off analysis, CI/CD design, team scalability, test data strategy |
| **Communication** | 10% | Video clarity, architecture explanation, extensibility demo, documentation quality |

### What Will Disqualify Your Submission

The following patterns indicate fundamental issues and will result in
automatic failure:

| Pattern | Why |
|---------|-----|
| `time.sleep()` in test or page code | Shows no understanding of wait strategies |
| No abstraction layer (raw Selenium in page objects and tests) | This is an SDET-level solution, not an architect-level one |
| Hardcoded credentials in source code | Security anti-pattern |
| Tests cannot execute at all (`pytest` crashes with import/config errors) | Cannot deliver a working system |
| Cannot explain your own architecture in the video | Raises authorship concerns |
| Tests target an application other than SauceDemo | Does not follow requirements |
| No ADR and no video submitted | An architect who doesn't document doesn't communicate |

---

## Submission

1. **Ensure all tests pass:** `pytest -v` should show all green
2. **Include your ADR:** `ADR.md` at the repo root (or clearly linked location)
3. **Record your video:** 10–15 minutes, upload to Google Drive/Loom/YouTube
4. **Create a `SUBMISSION.md`** at the repo root with:
   - Video demo link
   - Time spent on each task
   - Any assumptions or trade-offs you made
   - What you would improve given more time
5. **Commit and push** your code to your branch

---

## What You're Starting With

```
qa-architect-assignment/
├── README.md                     ← You are here
├── SCENARIO.md                   ← Read this first — the product you're designing for
├── requirements-baseline.txt     ← The only hard constraint (Python 3.10+, pytest)
├── .gitignore
│
└── ... everything else is YOURS TO BUILD
```

You decide the folder structure, the libraries, the patterns, and the
conventions. **Show us how you think.**
