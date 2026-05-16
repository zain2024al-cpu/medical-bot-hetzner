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
    # Denoise — NLMeans (0 = off)
    denoise_strength: int = 5             # keep low (3–7) to preserve handwriting
    # CLAHE contrast
    clahe_clip_limit: float = 1.8         # 1.0–2.5; higher = more contrast
    clahe_tile_grid: tuple = (8, 8)
    # Sharpening — unsharp mask (0.0 = off, 1.0 = strong)
    sharpen_strength: float = 0.25        # CONSERVATIVE — preserves stamps & Arabic
    # Gamma
    gamma: float = 1.0                    # 1.0 = no change; < 1 brighter
    # Illumination normalisation (removes uneven lighting)
    illumination_normalize: bool = True

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
