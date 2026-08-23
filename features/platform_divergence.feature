@platform-divergence
Feature: Interactions that only some platforms have
  Most of StreamCart behaves identically everywhere, but some interactions
  exist only on some platforms: a physical keyboard on the web, swiping on
  touch devices, a d-pad on televisions. Scenarios tagged @requires:<capability>
  run where the platform supports the interaction and are skipped — with the
  reason shown in the report — everywhere else.

  @requires:keyboard @TC-DIV-001
  Scenario: Signing in by pressing Enter on a physical keyboard
    Given the customer is on the sign-in screen
    When the customer signs in as "standard" using the keyboard
    Then the customer sees the products screen

  @requires:swipe @TC-DIV-002
  Scenario: Swiping through the catalogue on a touch screen
    Given the customer is signed in as "standard"
    When the customer swipes up through the products
    Then the customer sees 6 products
