"""
World Cup strategies: auto-import all modules in this package so they register.
Adding a new strategy = add a .py file with @register_strategy + add its id to config.yaml.
"""
import importlib
import pkgutil

for _importer, mod_name, _ in pkgutil.iter_modules(__path__, prefix=""):
    if mod_name != "__init__":
        importlib.import_module(f".{mod_name}", __name__)
