from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    image_dir: str = "/mnt/nas/photos"
    db_path: str = "/data/photo_curator.db"
    device: str = "cuda"

    clip_model: str = "ViT-L-14"
    clip_pretrained: str = "laion2b_s32b_b82k"
    aesthetic_predictor_weights: str = "/models/sac+logos+ava1-l14-linearMSE.pth"

    batch_size: int = 32
    thumbnail_size: int = 512
    max_phash_distance: int = 8
    export_dpi: int = 300

    aesthetic_weight: float = 0.50
    sharpness_weight: float = 0.25
    exposure_weight: float = 0.15
    face_bonus_weight: float = 0.10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
