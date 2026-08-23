@cart
Feature: Reviewing the cart
  The cart lists every product the customer added with its price and quantity.
  From here the customer can remove products, go back to shopping, or start checking out.

  Background:
    Given the customer is signed in as "standard"
    And the customer has added "Sauce Labs Backpack" and "Sauce Labs Bike Light" to the cart
    And the customer has opened the cart

  @smoke @TC-CART-001
  Scenario: The cart lists each product with its details
    Then the cart contains:
      | product               | price | quantity |
      | Sauce Labs Backpack   | 29.99 | 1        |
      | Sauce Labs Bike Light | 9.99  | 1        |

  @TC-CART-002
  Scenario: A product can be removed from the cart
    When the customer removes "Sauce Labs Bike Light" from the cart
    Then the cart contains only "Sauce Labs Backpack"
    And the cart badge shows 1

  @TC-CART-003
  Scenario: The customer can go back to shopping
    When the customer continues shopping
    Then the customer sees the products screen

  @TC-CART-004
  Scenario: The customer can proceed to checkout
    When the customer proceeds to checkout
    Then the customer sees the checkout information screen
