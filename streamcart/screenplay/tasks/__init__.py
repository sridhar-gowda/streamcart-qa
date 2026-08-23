"""Tasks — what actors do, in StreamCart's language.

Every Task leaves the UI in a settled state (it waits for the screen it
expects) so the next Task or Question never races a transition.
"""

from streamcart.screenplay.tasks.cart import ContinueShopping, OpenCart, ProceedToCheckout, RemoveFromCart
from streamcart.screenplay.tasks.checkout import (
    CancelCheckout,
    CompletePurchase,
    EnterShippingInformation,
    FinishOrder,
    ReturnToProducts,
)
from streamcart.screenplay.tasks.inventory import AddToCart, SortInventory, SwipeThroughProducts
from streamcart.screenplay.tasks.navigation import Open
from streamcart.screenplay.tasks.session import Login, Logout, ResetAppState

__all__ = [
    "AddToCart",
    "CancelCheckout",
    "CompletePurchase",
    "ContinueShopping",
    "EnterShippingInformation",
    "FinishOrder",
    "Login",
    "Logout",
    "Open",
    "OpenCart",
    "ProceedToCheckout",
    "RemoveFromCart",
    "ResetAppState",
    "ReturnToProducts",
    "SortInventory",
    "SwipeThroughProducts",
]
