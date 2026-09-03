#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("contract_dependencies.py")
SPEC = importlib.util.spec_from_file_location("contract_dependencies", MODULE_PATH)
assert SPEC and SPEC.loader
contract_dependencies = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contract_dependencies)

ContractGraphError = contract_dependencies.ContractGraphError
validate_graph = contract_dependencies.validate_graph


def graph(*, contracts):
    return {"schema_version": 1, "contracts": contracts}


class ContractDependenciesTest(unittest.TestCase):
    def test_valid_mode_scoped_edge(self) -> None:
        validate_graph(
            graph(
                contracts={
                    "1086": {
                        "dependencies": [{"issue": 1083, "modes": ["delivery"]}],
                    }
                }
            )
        )

    def test_invalid_mode_fails(self) -> None:
        with self.assertRaisesRegex(ContractGraphError, "invalid mode"):
            validate_graph(
                graph(
                    contracts={
                        "1086": {
                            "dependencies": [{"issue": 1083, "modes": ["cleanup"]}],
                        }
                    }
                )
            )

    def test_self_dependency_fails(self) -> None:
        with self.assertRaisesRegex(ContractGraphError, "cannot depend on itself"):
            validate_graph(
                graph(
                    contracts={
                        "1086": {
                            "dependencies": [{"issue": 1086, "modes": ["delivery"]}],
                        }
                    }
                )
            )

    def test_malformed_issue_identifier_fails(self) -> None:
        for contracts in (
            {"issue-1086": {"dependencies": [{"issue": 1083, "modes": ["delivery"]}]}},
            {"1086": {"dependencies": [{"issue": 0, "modes": ["delivery"]}]}},
        ):
            with self.subTest(contracts=contracts):
                with self.assertRaises(ContractGraphError):
                    validate_graph(graph(contracts=contracts))

    def test_duplicate_target_fails_instead_of_splitting_modes(self) -> None:
        with self.assertRaisesRegex(ContractGraphError, "repeats dependency target"):
            validate_graph(
                graph(
                    contracts={
                        "1086": {
                            "dependencies": [
                                {"issue": 1083, "modes": ["evaluation"]},
                                {"issue": 1083, "modes": ["delivery"]},
                            ],
                        }
                    }
                )
            )

    def test_same_mode_cycle_fails(self) -> None:
        with self.assertRaisesRegex(ContractGraphError, "delivery dependency cycle"):
            validate_graph(
                graph(
                    contracts={
                        "1083": {
                            "dependencies": [{"issue": 1086, "modes": ["delivery"]}],
                        },
                        "1086": {
                            "dependencies": [{"issue": 1083, "modes": ["delivery"]}],
                        },
                    }
                )
            )

    def test_cross_mode_back_edge_is_not_a_cycle(self) -> None:
        validate_graph(
            graph(
                contracts={
                    "1083": {
                        "dependencies": [{"issue": 1086, "modes": ["evaluation"]}],
                    },
                    "1086": {
                        "dependencies": [{"issue": 1083, "modes": ["delivery"]}],
                    },
                }
            )
        )

    def test_extra_metadata_is_rejected(self) -> None:
        with self.assertRaisesRegex(ContractGraphError, "extra"):
            validate_graph(
                {
                    "schema_version": 1,
                    "contracts": {
                        "1086": {
                            "dependencies": [{"issue": 1083, "modes": ["delivery"]}],
                            "owner": "someone",
                        }
                    },
                }
            )


if __name__ == "__main__":
    unittest.main()
