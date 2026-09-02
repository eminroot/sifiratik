"""GUS-DEDEKTIV model katmani (ARCHITECTURE.md Katman 3-5).

`gus_generator` veriyi uretir; bu paket o veriden dedektoru kurar. Ikisi
bilincli olarak ayridir: uretici latent buyuklukler uzerinde calisir, dedektor
yalnizca gozlenen alanlari gorur ve latent beklentiyi CIKARSAMAK zorundadir.
"""

from .config import MODEL_VERSION, ModelConfig
from .dataset import Bundle, load_bundle, split_report
from .pipeline import GusModel

__all__ = [
    "MODEL_VERSION",
    "ModelConfig",
    "Bundle",
    "GusModel",
    "load_bundle",
    "split_report",
]
