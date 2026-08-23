@inventory
Feature: Browsing the products
  The catalogue shows every product with its name, description, price and
  image. Customers can sort it by name or price and add products to the cart
  directly from the catalogue; the cart badge always reflects what is in the cart.

  Background:
    Given the customer is signed in as "standard"

  @smoke @TC-INV-001
  Scenario: The catalogue shows every product with its details
    Then the customer sees 6 products
    And every product shows a name, a description, a price and an image
    And the products match the catalogue

  @TC-INV-002
  Scenario Outline: The products can be sorted
    When the customer sorts the products by "<order>"
    Then the products are listed by <attribute> <direction>

    Examples:
      | order               | attribute | direction  |
      | Name (A to Z)       | name      | ascending  |
      | Name (Z to A)       | name      | descending |
      | Price (low to high) | price     | ascending  |
      | Price (high to low) | price     | descending |

  @smoke @TC-INV-003
  Scenario: Adding a product updates the cart badge
    When the customer adds "Sauce Labs Backpack" to the cart
    Then the cart badge shows 1
    And "Sauce Labs Backpack" is marked as in the cart

  @TC-INV-004
  Scenario: A product can be removed again from the catalogue
    Given the customer has added "Sauce Labs Backpack" to the cart
    When the customer removes "Sauce Labs Backpack" from the cart
    Then the cart badge shows 0
    And "Sauce Labs Backpack" is no longer marked as in the cart

  @TC-INV-005
  Scenario: The cart keeps its contents while the customer keeps browsing
    Given the customer has added "Sauce Labs Backpack" and "Sauce Labs Bike Light" to the cart
    When the customer opens the cart
    And the customer continues shopping
    Then the cart badge shows 2
    And "Sauce Labs Bike Light" is marked as in the cart
