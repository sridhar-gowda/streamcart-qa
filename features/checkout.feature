@checkout
Feature: Checking out
  Checkout takes three steps: shipping information, an order overview with the
  totals, and a confirmation. Every shipping field is required, and the
  overview's totals must reconcile: item total plus tax equals the total.

  Background:
    Given the customer is signed in as "standard"
    And the customer has added "Sauce Labs Backpack" and "Sauce Labs Bike Light" to the cart
    And the customer has proceeded to checkout

  @TC-CHK-001
  Scenario Outline: Every shipping field is required
    When the customer enters shipping information with first name "<first_name>", last name "<last_name>" and postal code "<postal_code>"
    Then the customer sees the checkout information screen
    And the checkout error says "<message>"

    Examples:
      | first_name | last_name | postal_code | message                 |
      |            | Lovelace  | SW1A 1AA    | First Name is required  |
      | Ada        |           | SW1A 1AA    | Last Name is required   |
      | Ada        | Lovelace  |             | Postal Code is required |

  @smoke @TC-CHK-002
  Scenario: The order overview reconciles the totals
    When the customer enters shipping information with first name "Ada", last name "Lovelace" and postal code "SW1A 1AA"
    Then the customer sees the checkout overview screen
    And the overview lists "Sauce Labs Backpack" and "Sauce Labs Bike Light"
    And the item total is the sum of the listed prices
    And the tax is 8% of the item total
    And the total is the item total plus tax

  @smoke @critical @TC-CHK-003
  Scenario: A completed order is confirmed
    When the customer enters shipping information with first name "Ada", last name "Lovelace" and postal code "SW1A 1AA"
    And the customer finishes the order
    Then the customer sees the order confirmation
    And the confirmation says "Thank you for your order!"

  @TC-CHK-004
  Scenario: Checkout can be cancelled back to the cart
    When the customer cancels the checkout
    Then the customer sees the cart screen
