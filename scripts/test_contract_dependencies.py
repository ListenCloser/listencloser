#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from contract_dependencies import ContractGraphError, validate_graph

VALID = {
    "schema_version": 1,
    "contracts": {
        "1086": {
            "dependencies": [{"issue": 1083, "modes": ["delivery"]}],
        }
    },
}


class ContractDependenciesTest(unittest.TestCase):
    def invalid(self, data, message: str | None = None) -> None:
        with self.assertRaisesRegex(ContractGraphError, message or ".*"):
            validate_graph(data)

    def test_valid_mode_scoped_edge(self) -> None:
        validate_graph(VALID)

    def test_invalid_mode_fails(self) -> None:
        data = copy.deepcopy(VALID)
        data["contracts"]["1086"]["dependencies"][0]["modes"] = ["cleanup"]
        self.invalid(data, "invalid mode")

    def test_self_dependency_fails(self) -> None:
        data = copy.deepcopy(VALID)
        data["contracts"]["1086"]["dependencies"][0]["issue"] = 1086
        self.invalid(data, "cannot depend on itself")

    def test_malformed_issue_identifiers_fail(self) -> None:
        bad_source = copy.deepcopy(VALID)
        bad_source["contracts"]["issue-1086"] = bad_source["contracts"].pop("1086")
        self.invalid(bad_source, "invalid contract issue id")

        bad_target = copy.deepcopy(VALID)
        bad_target["contracts"]["1086"]["dependencies"][0]["issue"] = 0
        self.invalid(bad_target, "positive integer")

    def test_duplicate_target_fails(self) -> None:
        data = copy.deepcopy(VALID)
        data["contracts"]["1086"]["dependencies"].append(
            {"issue": 1083, "modes": ["evaluation"]}
        )
        self.invalid(data, "repeats target")

    def test_same_mode_cycle_fails(self) -> None:
        data = {
            "schema_version": 1,
            "contracts": {
                "1083": {"dependencies": [{"issue": 1086, "modes": ["delivery"]}]},
                "1086": {"dependencies": [{"issue": 1083, "modes": ["delivery"]}]},
            },
        }
        self.invalid(data, "delivery dependency cycle")

    def test_cross_mode_back_edge_is_not_a_cycle(self) -> None:
        validate_graph(
            {
                "schema_version": 1,
                "contracts": {
                    "1083": {
                        "dependencies": [{"issue": 1086, "modes": ["evaluation"]}]
                    },
                    "1086": {
                        "dependencies": [{"issue": 1083, "modes": ["delivery"]}]
                    },
                },
            }
        )

    def test_extra_metadata_is_rejected(self) -> None:
        data = copy.deepcopy(VALID)
        data["contracts"]["1086"]["owner"] = "someone"
        self.invalid(data, "keys must be exactly")


if __name__ == "__main__":
    unittest.main()
