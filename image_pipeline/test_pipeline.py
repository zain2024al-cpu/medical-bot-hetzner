"""
Quick local test — run with:
    python -m image_pipeline.test_pipeline path/to/image.jpg

Processes the image through the full pipeline and saves:
  image_pipeline/debug/test_p00_original.jpg
  image_pipeline/debug/test_p00_cropped.jpg
  image_pipeline/debug/test_p00_enhanced.jpg
  image_pipeline/debug/test_final.pdf
"""

import sys
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-8s %(name)s — %(message)s",
)


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m image_pipeline.test_pipeline <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        sys.exit(1)

    with open(image_path, "rb") as f:
        raw = f.read()

    from image_pipeline.pipeline import run_pipeline
    from image_pipeline.config import DEFAULT_CONFIG

    # Force debug on
    DEFAULT_CONFIG.debug.enabled = True
    DEFAULT_CONFIG.debug.output_dir = os.path.join(
        os.path.dirname(__file__), "debug"
    )
    os.makedirs(DEFAULT_CONFIG.debug.output_dir, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"  Input : {image_path}")
    print(f"  Debug : {DEFAULT_CONFIG.debug.output_dir}")
    print(f"{'='*50}\n")

    pdf = run_pipeline([raw], config=DEFAULT_CONFIG, job_id="test")

    out_path = os.path.join(DEFAULT_CONFIG.debug.output_dir, "test_output.pdf")
    with open(out_path, "wb") as f:
        f.write(pdf.read())

    print(f"\n✅ Done — output PDF: {out_path}")
    print(f"   Debug images: {DEFAULT_CONFIG.debug.output_dir}/")


if __name__ == "__main__":
    main()
