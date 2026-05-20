# image_pipeline/config.py
# All tunables in one place — change here, affects the entire pipeline.

from dataclasses import dataclass, field
import os

# ---------------------------------------------------------------------------
# Stage toggles & knobs
# ---------------------------------------------------------------------------

@dataclass
class DetectorConfig:
    enabled: bool = True
    model_path: str = "yolov8n-seg.pt"   # auto-downloaded on first run
    confidence: float = 0.35
    iou_threshold: float = 0.45
    min_area_ratio: float = 0.15          # ignore detections < 15% of image area
    fallback_on_failure: bool = True

@dataclass
class CropperConfig:
    enabled: bool = True
    padding_ratio: float = 0.02           # 2% padding around document edges
    safe_margin_px: int = 8               # never go closer than N px to image border

@dataclass
class CorrectorConfig:
    enabled: bool = True
    max_warp_angle_deg: float = 45.0      # skip correction if tilt is extreme
    min_quad_area_ratio: float = 0.20

@dataclass
class EnhancerConfig:
    enabled: bool = True
    # Adaptive quality-based processing (recommended: True)
    # When True, the tier-param table in enhancer.py overrides the values below.
    # When False, the values below are used directly for every image.
    adaptive_enhance: bool = True
    # --- Fallback values used when adaptive_enhance=False ---
    # Denoise — NLMeans (0 = off); keep ≤ 5 to preserve handwriting
    denoise_strength: int = 3
    # CLAHE contrast; 1.0–2.0 safe range for medical docs
    clahe_clip_limit: float = 1.2
    clahe_tile_grid: tuple = (8, 8)
    # Sharpening — unsharp mask (0.0 = off); ≤ 0.20 for medical docs
    sharpen_strength: float = 0.15
    # Gamma (1.0 = no change; < 1.0 brightens)
    gamma: float = 1.0
    # Illumination normalisation blend fraction (0.0 = off, 1.0 = full replacement)
    # Values below 0.5 preserve natural document appearance
    illumination_normalize: bool = True
    illum_blend: float = 0.45

@dataclass
class PDFConfig:
    jpeg_quality: int = 92
    jpeg_subsampling: int = 0             # 0 = 4:4:4 (best quality)
    max_dimension_px: int = 3840          # rescale very large images before PDF

@dataclass
class DebugConfig:
    enabled: bool = True
    output_dir: str = os.path.join(os.path.dirname(__file__), "debug")

@dataclass
class PipelineConfig:
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    cropper: CropperConfig = field(default_factory=CropperConfig)
    corrector: CorrectorConfig = field(default_factory=CorrectorConfig)
    enhancer: EnhancerConfig = field(default_factory=EnhancerConfig)
    pdf: PDFConfig = field(default_factory=PDFConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)


# Module-level singleton — import this everywhere
DEFAULT_CONFIG = PipelineConfig()
