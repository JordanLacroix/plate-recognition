"""Export .pt -> .onnx. Étape obligatoire du chemin de portabilité Jetson.

ONNX opset stable, batch dynamique off (POC), shapes fixes -> TensorRT plus simple.
Sur Jetson: onnx -> trtexec (INT8/FP16). Ne pas coder TensorRT ici.
"""

from __future__ import annotations

from pathlib import Path


def export_onnx(weights: str | Path, out: str | Path, imgsz: int = 640, opset: int = 17) -> Path:
    import torch

    from anpr_poc.detect.libreyolo import TorchDetector

    det = TorchDetector(weights, device="cpu")
    model = det._model  # forward isolé
    dummy = torch.zeros(1, 3, imgsz, imgsz)
    out = Path(out)
    torch.onnx.export(
        model,
        dummy,
        str(out),
        opset_version=opset,
        input_names=["images"],
        output_names=["output"],
        dynamic_axes=None,  # shapes fixes pour TensorRT
    )
    return out


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("weights")
    p.add_argument("out")
    p.add_argument("--imgsz", type=int, default=640)
    a = p.parse_args()
    print(export_onnx(a.weights, a.out, a.imgsz))
