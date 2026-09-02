"""GUS-DEDEKTIV sentetik dataset ureteci.

KinetiX / TEKNOFEST 2026 Sifir Atik ve Dongusel Ekonomi.

Katmanlar:
  A - Gercek acik veriler        (data/reference/*.csv, kaynakli)
  B - Sentetik firma verisi      (entities.py, observations.py)
  C - Sentetik audit ground-truth(anomalies.py)

Tum sentetik icerik `is_synthetic` / `data_source_type` alanlariyla isaretlidir.
"""

from .config import GeneratorConfig, DATASET_VERSION, SCHEMA_VERSION
from .pipeline import build_dataset, DatasetBundle

__all__ = ["GeneratorConfig", "DATASET_VERSION", "SCHEMA_VERSION", "build_dataset", "DatasetBundle"]
__version__ = DATASET_VERSION
