@failure-simulation
Feature: Failure simulation - one scenario per outcome the reports can show
  These scenarios exist only to produce an example report set (a simulation, not product behaviour). Each one ends in a
  different outcome on purpose: a pass, a product defect, a missing element, an
  environment failure that passes on retry, a known issue, a quarantined scenario
  and a scenario the platform cannot run. They are not part of the product suite.

  Background:
    Given the customer is signed in as "standard"

  @smoke @TC-DEMO-001
  Scenario: A passing scenario
    When the customer adds "Sauce Labs Backpack" to the cart
    Then the cart badge shows 1

  @TC-DEMO-002
  Scenario: A product defect - the badge count is wrong (simulated by expecting 2)
    When the customer adds "Sauce Labs Backpack" to the cart
    Then the cart badge shows 2

  @TC-DEMO-003
  Scenario: A UI contract failure - the product the test expects does not exist
    When the customer adds "Sauce Labs Teleporter" to the cart
    Then the cart badge shows 1

  @TC-DEMO-004
  Scenario: An environment failure that passes on retry - reported as flaky
    When the browser session drops once
    And the customer adds "Sauce Labs Backpack" to the cart
    Then the cart badge shows 1

  @known_issue:SC-42 @TC-DEMO-005
  Scenario: A known issue tracked in ticket SC-42 - fails without blocking the build
    When the customer adds "Sauce Labs Backpack" to the cart
    Then the cart badge shows 3

  @quarantine @TC-DEMO-006
  Scenario: A quarantined scenario - fails without blocking the build
    When the customer adds "Sauce Labs Backpack" to the cart
    Then the cart badge shows 4

  @requires:swipe @TC-DEMO-007
  Scenario: A scenario this platform cannot run - skipped with the reason
    When the customer swipes up through the products
    Then the cart badge shows 0
