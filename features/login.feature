@login
Feature: Signing in
  Customers sign in with their StreamCart account before they can shop.
  Wrong or missing credentials are reported on the sign-in screen, and a
  locked account is refused with a specific message so the customer knows
  to contact support rather than retry.

  Background:
    Given the customer is on the sign-in screen

  @smoke @critical @TC-LOGIN-001
  Scenario: A customer with valid credentials reaches the products
    When the customer signs in as "standard"
    Then the customer sees the products screen

  @TC-LOGIN-002
  Scenario: Wrong credentials are refused
    When the customer signs in with username "standard_user" and password "not-the-password"
    Then the customer stays on the sign-in screen
    And the sign-in error says "Username and password do not match any user in this service"

  @TC-LOGIN-003
  Scenario: A locked-out account is refused with a specific message
    When the customer signs in as "locked_out"
    Then the customer stays on the sign-in screen
    And the sign-in error says "Sorry, this user has been locked out."

  @TC-LOGIN-004
  Scenario Outline: Missing credentials are reported
    When the customer signs in with username "<username>" and password "<password>"
    Then the customer stays on the sign-in screen
    And the sign-in error says "<message>"

    Examples:
      | username      | password | message              |
      |               | anything | Username is required |
      | standard_user |          | Password is required |

  @TC-LOGIN-005
  Scenario Outline: Every active account type can sign in
    When the customer signs in as "<persona>"
    Then the customer sees the products screen

    Examples:
      | persona  |
      | standard |
      | problem  |
      | error    |
      | visual   |

  @slow @TC-LOGIN-006
  Scenario: An account with slow responses can still sign in
    The performance_glitch persona simulates a throttled backend. It is a
    resilience check, not a functional one, so it is tagged @slow and kept
    out of the PR gate.

    When the customer signs in as "performance_glitch"
    Then the customer sees the products screen
