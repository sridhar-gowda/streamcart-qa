"""Reference data: personas and the product catalogue.

Three kinds of test data exist in this framework and they deliberately live in
different places:

- **secrets** (passwords, tokens): the environment only — ``.env`` locally, CI secrets
  in pipelines; see ``Settings.users``;
- **reference data** (who the personas are, what the catalogue contains): this
  package, loaded from ``data/*.yaml``, versioned with the tests, platform-agnostic;
- **scenario data** (which fields are left blank in a validation case): the
  ``Examples`` tables of the feature files themselves.
"""

from streamcart.testdata.personas import Persona, PersonaCatalogue
from streamcart.testdata.products import Product, ProductCatalogue

__all__ = ["Persona", "PersonaCatalogue", "Product", "ProductCatalogue"]
