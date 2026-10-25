import sys
import os
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.services.data_engineering.importer import import_complaint_csv

app = create_app(os.getenv("FLASK_ENV", "development"))


def main():
    parser = argparse.ArgumentParser(description="CIVICLENS AI Municipal CSV Dataset Importer")
    parser.add_argument("csv_path", help="Path to CSV dataset file")
    parser.add_argument("--source", default="CLI_IMPORT", help="Data source tag (e.g. NYC_311, CITY_PORTAL)")
    parser.add_argument("--synthetic", action="store_true", help="Flag whether records are synthetic")
    args = parser.parse_args()

    csv_file = Path(args.csv_path)
    if not csv_file.exists():
        print(f"Error: File not found at '{args.csv_path}'")
        sys.exit(1)

    print(f"Ingesting dataset from '{csv_file.name}' [Source: {args.source}]...")

    with app.app_context():
        with open(csv_file, "r", encoding="utf-8", errors="replace") as f:
            result = import_complaint_csv(
                file_stream=f,
                filename=csv_file.name,
                source=args.source,
                is_synthetic=args.synthetic,
            )

        if result.get("success"):
            print("\n" + "=" * 50)
            print("  CSV INGESTION BATCH COMPLETED")
            print("=" * 50)
            print(f"Batch ID:        #{result['batch_id']}")
            print(f"Total Rows:      {result['total_rows']}")
            print(f"Accepted Rows:   {result['accepted_rows']}")
            print(f"Rejected Rows:   {result['rejected_rows']}")

            if result["rejections"]:
                print("\nQuarantined Row Samples (Top 5):")
                for r in result["rejections"][:5]:
                    print(f"  Line {r['row']}: {r['reason']}")
            print("\nDataset imported successfully and persisted to database.")
        else:
            print(f"\nImport Failed: {result.get('error')}")
            sys.exit(1)


if __name__ == "__main__":
    main()
