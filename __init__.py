from . import models
from . import wizards

# Re-export the pre_init_hook so Odoo's manifest loader can find it
# at the top of the module namespace.
from .models.install_hooks import pre_init_check  # noqa: F401
