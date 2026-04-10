"""
detectors - Modular signal detector loader.

Provides auto-discovery of detector modules. Drop a new file under this
directory containing BaseDetector subclasses, and it will be picked up
automatically by all_detectors().
"""

import importlib
import inspect
import pkgutil

from .base import BaseDetector


def all_detectors():
    """
    Return instantiated instances of all BaseDetector subclasses defined
    in modules under this package.

    Walks the detectors/ directory, imports each module, and collects
    every concrete BaseDetector subclass. Excludes the base module itself.
    """
    detectors = []
    package_path = __path__
    package_name = __name__

    for _, module_name, _ in pkgutil.iter_modules(package_path):
        if module_name in ('base', '__init__'):
            continue

        module = importlib.import_module(f"{package_name}.{module_name}")

        for _, obj in inspect.getmembers(module, inspect.isclass):
            # Only collect concrete subclasses defined in this module
            # (skip BaseDetector itself and any imported classes)
            if (issubclass(obj, BaseDetector)
                    and obj is not BaseDetector
                    and obj.__module__ == module.__name__):
                detectors.append(obj())

    return detectors


__all__ = ['BaseDetector', 'all_detectors']
