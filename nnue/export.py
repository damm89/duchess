import struct
import torch
import sys
from model import HalfKP

def export_nnue(model_path, output_path):
    print(f"Loading {model_path}...")
    model = HalfKP()
    model.load_state_dict(torch.load(model_path, map_location='cpu'))
    model.eval()

    # Define quantization scales
    # FT is quantized to int16. Scale = 255
    SCALE_QA = 255.0
    # FC layers are quantized to int8. Scale = 64
    SCALE_QB = 64.0

    print(f"Exporting to {output_path}...")
    with open(output_path, 'wb') as f:
        # 1. Magic Number 'DUCH' (0x48435544)
        f.write(struct.pack('<I', 0x48435544))
        # 2. Version 1
        f.write(struct.pack('<I', 1))

        # 3. FT Weights (41024, 256) -> int16
        print("Writing ft_weights...")
        ft_w = (model.ft_weights.weight.detach() * SCALE_QA).round().to(torch.int16)
        # Flattened row by row, or column by column? 
        # C++ typically expects [41024][256] flat:
        f.write(ft_w.numpy().tobytes())

        # 4. FT Bias (256) -> int16
        print("Writing ft_bias...")
        ft_b = (model.ft_bias.detach() * SCALE_QA).round().to(torch.int16)
        f.write(ft_b.numpy().tobytes())

        # 5. FC1 Weights (128, 512) -> int8
        print("Writing fc1.weight...")
        fc1_w = (model.fc1.weight.detach() * SCALE_QB).round().to(torch.int8)
        f.write(fc1_w.numpy().tobytes())

        # 6. FC1 Bias (128) -> int32
        print("Writing fc1.bias...")
        fc1_b = (model.fc1.bias.detach() * SCALE_QA * SCALE_QB).round().to(torch.int32)
        f.write(fc1_b.numpy().tobytes())

        # 7. FC2 Weights (128, 128) -> int8
        print("Writing fc2.weight...")
        fc2_w = (model.fc2.weight.detach() * SCALE_QB).round().to(torch.int8)
        f.write(fc2_w.numpy().tobytes())

        # 8. FC2 Bias (128) -> int32
        print("Writing fc2.bias...")
        # Actually in standard HalfKP, the accumulator after FC1 is clipped 0-127 (or 0-255).
        # We did clamp(0, 1) in PyTorch, which is 0-127 in int8 space.
        # Thus the input to FC2 has scale (QA * QB) / QA = QB ?
        # Standard approach:
        fc2_b = (model.fc2.bias.detach() * SCALE_QA * SCALE_QB).round().to(torch.int32)
        f.write(fc2_b.numpy().tobytes())

        # 9. Out Weights (1, 128) -> int8
        print("Writing out.weight...")
        out_w = (model.out.weight.detach() * SCALE_QB).round().to(torch.int8)
        f.write(out_w.numpy().tobytes())

        # 10. Out Bias (1) -> int32
        print("Writing out.bias...")
        # The output bias should be scaled so that when divided at the end, it produces cp.
        # Our target score is scaled through sigmoid...
        # Traditional NNUE uses simple MSE on eval. 
        # Let's just output raw int32 and scale in C++.
        out_b = (model.out.bias.detach() * SCALE_QA * SCALE_QB).round().to(torch.int32)
        f.write(out_b.numpy().tobytes())

    print("Export complete.")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python export.py <model.pt> <output.bin>")
        sys.exit(1)
    export_nnue(sys.argv[1], sys.argv[2])
