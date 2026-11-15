"""Manual smoke check: run a Bell-state experiment through the SDK against a live server.

This is not an automated test. Start the server first, then:

    uv run python scripts/demo_bell.py
"""

from __future__ import annotations

import argparse

from quantum_sdk import QuantumClient


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default="test-key")
    parser.add_argument("--shots", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    with QuantumClient(base_url=args.base_url, api_key=args.api_key) as client:
        experiment = client.create_experiment(
            name="bell_state", qubits=2, shots=args.shots, seed=args.seed
        )
        experiment.add_gate("H", target=0)
        experiment.add_gate("CNOT", control=0, target=1)

        result = client.run(experiment)

        print(f"experiment: {result.experiment_id}")
        print(f"counts:     {result.counts}")
        print(f"history:    {client.list_experiments(limit=5).total} experiment(s) for this key")


if __name__ == "__main__":
    main()
