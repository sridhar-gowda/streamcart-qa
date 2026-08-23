"""Signing in."""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from streamcart.screenplay import Actor
from streamcart.screenplay.questions import TheLoginError
from streamcart.screenplay.tasks import Login, Open
from streamcart.testdata import PersonaCatalogue
from streamcart.ui.pages import LoginPage


@given("the customer is on the sign-in screen")
def on_sign_in_screen(customer: Actor) -> None:
    customer.attempts_to(Open.the(LoginPage))


@given(parsers.parse('the customer is signed in as "{persona}"'))
@when(parsers.parse('the customer signs in as "{persona}"'))
def signs_in_as(customer: Actor, personas: PersonaCatalogue, persona: str) -> None:
    customer.attempts_to(Login.as_(personas.resolve(persona)))


@when(parsers.parse('the customer signs in as "{persona}" using the keyboard'))
def signs_in_with_keyboard(customer: Actor, personas: PersonaCatalogue, persona: str) -> None:
    customer.attempts_to(Login.as_(personas.resolve(persona)).submitting_with_the_keyboard())


@when(parsers.re(r'the customer signs in with username "(?P<username>[^"]*)" and password "(?P<password>[^"]*)"'))
def signs_in_with(customer: Actor, username: str, password: str) -> None:
    customer.attempts_to(Login.with_credentials(username, password))


@then(parsers.parse('the sign-in error says "{message}"'))
def sign_in_error_says(customer: Actor, message: str) -> None:
    error = customer.asks(TheLoginError())
    assert error is not None, "expected a sign-in error, but none is shown"
    assert message in error
