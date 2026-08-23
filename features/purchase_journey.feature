@journey
Feature: The StreamCart purchase journey
  The same journey on every platform: sign in, browse, add to cart, review
  the cart, check out, and get a confirmation. This is the scenario that must
  never break.

  @smoke @e2e @critical @TC-E2E-001
  Scenario: A customer buys a backpack end to end
    Given the customer is on the sign-in screen
    When the customer signs in as "standard"
    And the customer adds "Sauce Labs Backpack" to the cart
    And the customer opens the cart
    And the customer proceeds to checkout
    And the customer enters shipping information with first name "Ada", last name "Lovelace" and postal code "SW1A 1AA"
    And the customer finishes the order
    Then the customer sees the order confirmation
    And the confirmation says "Thank you for your order!"
    When the customer returns to the products
    Then the customer sees the products screen
    And the cart badge shows 0
