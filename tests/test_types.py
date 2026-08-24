"""Tests for the UNSET sentinel."""

from __future__ import annotations

import copy
import pickle

from cloudy_salesforce.types import UNSET, UnsetType


def test_unset_is_falsy_singleton():
    assert UNSET is UnsetType()
    assert UnsetType() is UnsetType()
    assert bool(UNSET) is False
    assert (UNSET or "fallback") == "fallback"


def test_unset_survives_copy_and_pickle():
    copied = copy.copy(UNSET)
    deep = copy.deepcopy(UNSET)
    pickled = pickle.loads(pickle.dumps(UNSET))
    assert copied is UNSET
    assert deep is UNSET
    assert pickled is UNSET
