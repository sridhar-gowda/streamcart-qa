# Writing your first scenario

Product behaviour is written in Gherkin. The framework provides everything below the step line.
This is the path a new SDET follows on day one.

## 1. Describe the behaviour — `features/<area>.feature`

```gherkin
@inventory
Feature: Browsing the products

  Background:
    Given the customer is signed in as "standard"

  @smoke @TC-INV-003
  Scenario: Adding a product updates the cart badge
    When the customer adds "Sauce Labs Backpack" to the cart
    Then the cart badge shows 1
```

Tags are the whole control surface. You never write a pytest marker by hand.

| Tag | What it does |
|---|---|
| `@smoke` `@regression` `@e2e` | Which suites include the scenario (`--suite smoke`). No tag = regression. |
| `@web` `@ios` `@android` `@firetv` `@roku` `@appletv` | Run only on those platforms. No tag = every platform. |
| `@requires:swipe,dpad` | Skip, with the reason in the report, where the platform cannot do this. |
| `@critical` | Business-critical path: a failure pages someone instead of a quiet notification. |
| `@slow` | Deliberately slow scenario; kept out of the PR gate. |
| `@TC-INV-003` (any `ABC-123` style id) | The link to the test-management system. `--tms-plan` and `--tms-ids` select by it. |
| `@known_issue:SC-42` | Expected failure with a ticket. Reported as *known-issue*, never as a new defect. |
| `@quarantine` | Runs but cannot fail the build. A reviewed decision, visible in the feature file. |
| anything else (`@inventory`) | A label for the functional area. |

## 2. Bind the feature — `tests/steps/test_<area>.py`

```python
from pytest_bdd import scenarios

scenarios("inventory.feature")
```

That is the whole file. Step modules are registered once in the root `conftest.py`, so every
feature can use every step.

## 3. Write the steps — one line each

```python
@when(parsers.parse('the customer adds "{product}" to the cart'))
def adds_to_cart(customer: Actor, product: str) -> None:
    customer.attempts_to(AddToCart.item(product))


@then(parsers.parse("the cart badge shows {count:d}"))
def cart_badge_shows(customer: Actor, count: int) -> None:
    assert customer.asks(TheCartBadgeCount()) == count
```

The rule: a step is **one `attempts_to`, or one `asks` followed by an assertion**. No locators,
no waits, no page objects in a step. If you need more than one line, you need a Task or a Question.

Fixtures you get for free:

- `customer` — the Actor, already able to drive the current platform;
- `personas` — the users from `data/users.yaml` (passwords come from the environment);
- `products` — the product catalogue from `data/products.yaml`;
- `settings` and `run_id`.

## 4. Need a new Task? — `streamcart/screenplay/tasks/<area>.py`

A Task is something the user *does*, written in product language.

```python
class AddToCart(Task):
    """Add one product from the catalogue screen and wait until the badge reflects it."""

    def __init__(self, product: str) -> None:
        self.product = product

    @classmethod
    def item(cls, product: str) -> AddToCart:
        return cls(product)

    def perform_as(self, actor: Actor) -> None:
        inventory = InventoryPage(actor.driver)
        before = inventory.header.cart_badge.count()
        inventory.card_for(self.product).add_button.press()
        actor.driver.wait.until(
            lambda: inventory.header.cart_badge.count() == before + 1, message=f"cart badge after adding {self.product}"
        )
```

Tasks compose Pages and Components, and they **settle the UI** — they wait for the screen to
reach the expected state, so the step after them never has to wait. If a Task needs something
only some platforms can do, it says so (`self.requires = (Capability.SWIPE,)`) and the framework
skips the scenario where the platform cannot provide it.

## 5. Need a new Question? — `streamcart/screenplay/questions/<area>.py`

A Question is something the user can *find out*. It returns a typed value, never raw text.

```python
class TheCartBadgeCount(Question[int]):
    def answered_by(self, actor: Actor) -> int:
        return Header(actor.driver).cart_badge.count()
```

Typed answers (`int`, `Decimal`, a dataclass, an enum) keep the assertion in the step exact.

## 6. Need a new element? — the Page or Component it belongs to

```python
class InventoryPage(Page):
    PATH = "/inventory.html"
    SORT = Locator.test_id("sort control", "product-sort-container")
    MARKER = SORT
```

A `Locator` gives the element a human name and one selector per platform (or per family).
Pages hold locators and simple actions only: no assertions, no flows, no waiting beyond
`wait_until_displayed`.

## 6b. Adding a whole new screen — example: a payment screen

When the product grows a screen, the work is four small pieces, in this order. Nothing in the
framework changes. (SauceDemo has no payment screen, so this is a template to copy, not a runnable
example.)

**1. The Page** — `streamcart/ui/pages/payment.py`: the path, a marker element that only this
screen has, and the locators. Reuse components where the screen reuses UI.

```python
class PaymentPage(Page):
    PATH = "/payment.html"
    CARD_NUMBER = Locator.test_id("card number", "card-number")
    EXPIRY = Locator.test_id("expiry", "card-expiry")
    PAY_BUTTON = Locator.test_id("pay button", "pay")
    MARKER = PAY_BUTTON

    def __init__(self, driver: PlatformDriver) -> None:
        super().__init__(driver)
        self.card_number = TextField(driver, self.CARD_NUMBER)
        self.expiry = TextField(driver, self.EXPIRY)
        self.pay_button = Button(driver, self.PAY_BUTTON)
        self.error = ErrorBanner(driver)
```

Also register the screen in `streamcart/screenplay/questions/screen.py` (a `Screen.PAYMENT` value
and one row in the `_SCREENS` table) so `TheCurrentScreen()` can recognise it.

**2. The Task** — `streamcart/screenplay/tasks/payment.py`: what the user does, and what "done"
looks like.

```python
class PayWithCard(Task):
    def __init__(self, number: str, expiry: str) -> None:
        self.number, self.expiry = number, expiry

    def perform_as(self, actor: Actor) -> None:
        page = PaymentPage(actor.driver)
        page.card_number.type(self.number)
        page.expiry.type(self.expiry)
        page.pay_button.press()
        confirmation = CheckoutCompletePage(actor.driver)
        actor.driver.wait.until(
            lambda: confirmation.is_displayed() or page.error.is_displayed(),
            message="payment outcome (confirmation or an error message)",
        )
```

**3. The Question** — `streamcart/screenplay/questions/payment.py`: what the user can check, typed.

```python
class ThePaymentError(Question["str | None"]):
    def answered_by(self, actor: Actor) -> str | None:
        banner = PaymentPage(actor.driver).error
        return banner.message() if banner.is_displayed() else None
```

**4. The steps and the feature** — `tests/steps/payment_steps.py` (one line each) and
`features/payment.feature`; add the step module to `STEP_MODULES` in the root `conftest.py`.

```python
@when(parsers.parse('the customer pays with card "{number}" expiring "{expiry}"'))
def pays_with_card(customer: Actor, number: str, expiry: str) -> None:
    customer.attempts_to(PayWithCard(number, expiry))


@then(parsers.parse('the payment error says "{message}"'))
def payment_error_says(customer: Actor, message: str) -> None:
    assert message in (customer.asks(ThePaymentError()) or "")
```

```gherkin
@payment
Feature: Paying for the order

  @smoke @TC-PAY-001
  Scenario: A valid card completes the order
    Given the customer is on the payment screen with items in the cart
    When the customer pays with card "4111 1111 1111 1111" expiring "12/30"
    Then the customer sees the order confirmation
```

Selectors for other platforms come later, as extra keys on the same locators (`tv=...`,
`roku=...`); the Task, the Question and the steps do not change.

## 7. Run it and read the result

```bash
pytest -k "cart badge" --headed          # watch it in a browser window
pytest tests/steps/test_inventory.py      # one feature
pytest --suite smoke -n 4                 # what the PR gate runs
```

Open the run folder printed at the end of the run (`reports/runs/<run-id>/`) and then `report.html`. Every failure carries a **Category**:

| Category | What it means | Who should look |
|---|---|---|
| product | An assertion in a step failed: the application did the wrong thing. | the developer |
| ui-contract | An element was missing, not clickable, or never settled: a locator is stale or the UI changed. | the owner of that page |
| environment | The session, the network or the app was unavailable. Retried once automatically (the team can widen retries with `--retry-categories`). | infrastructure |
| test-defect | Wrong configuration or misuse of the framework. | you |
| flaky | Passed only on the retry. The retry hid a failure; the report does not. | the team, in the weekly review |

Screenshots, page source and console logs are captured at the moment of failure and linked
from every report. The full tour of the reports is in [reports.md](reports.md).

## The conventions in one breath

One feature file per area. One step per sentence, one line each. One Task per intention. One
Question per fact. One Page per screen, one Component per reusable piece. Tags instead of
markers. Only Tasks and adapters wait. Nothing sleeps, ever — `ruff` will tell you.
