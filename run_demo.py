from __future__ import annotations

from main import run_pipeline


def main():
    out = run_pipeline()

    multiples = out["multiples"]
    dcf = out["dcf"]["valuation"]

    print("\n==============================")
    print("NVDA Fundamental Agent Demo Run")
    print("==============================\n")

    print("Multiples (TTM):")
    try:
        print(multiples.round(2).to_markdown())
    except Exception:
        print(multiples.round(2).to_string())

    print("\nDCF valuation:")
    for k, v in dcf.items():
        print(f"- {k}: {v}")

    print("\nArtifacts:")
    print(f"- Memo: {out['memo_path']}")
    if out["figures"]:
        print("- Figures:")
        for p in out["figures"]:
            print(f"  - {p}")


if __name__ == "__main__":
    main()
