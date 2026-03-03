import json
import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import chess
from model import HalfKP, feature_index
import math
import argparse

class NNUEDataset(Dataset):
    def __init__(self, jsonl_file):
        self.data = []
        with open(jsonl_file, 'r') as f:
            for line in f:
                if line.strip():
                    self.data.append(json.loads(line))
                    
    def __len__(self):
        return len(self.data)
        
    def __getitem__(self, idx):
        row = self.data[idx]
        fen = row['fen']
        score_cp = row['score']
        
        # Sigmoid scaling trick for chess evaluation (often ~ 1 / (1 + exp(-score / 400)))
        # Clamp checkmate scores (-999999) to prevent math range overflows
        score_cp = max(-4000.0, min(4000.0, float(score_cp)))
        target = 1.0 / (1.0 + math.exp(-score_cp / 400.0))
        
        board = chess.Board(fen)
        us = board.turn
        them = not us
        
        # Find kings
        us_king_sq = board.king(us)
        them_king_sq = board.king(them)
        
        # Calculate active features
        us_features = []
        them_features = []
        
        # Piece types mapping (0..9)
        # White: P=0, N=1, B=2, R=3, Q=4
        # Black: P=5, N=6, B=7, R=8, Q=9
        for sq, piece in board.piece_map().items():
            if piece.piece_type == chess.KING:
                continue
                
            color_offset = 0 if piece.color == chess.WHITE else 5
            pt = piece.piece_type - 1 + color_offset
            
            # Feature from 'us' perspective
            us_ft = feature_index(us_king_sq, pt, sq)
            us_features.append(us_ft)
            
            # Feature from 'them' perspective
            # Flip the board horizontally/vertically for symmetry if needed, 
            # but standard HalfKP just uses absolute king and absolute piece sq
            them_ft = feature_index(them_king_sq, pt, sq)
            them_features.append(them_ft)
            
        return us_features, them_features, target

def collate_fn(batch):
    us_indices = []
    us_offsets = [0]
    them_indices = []
    them_offsets = [0]
    targets = []
    
    for us_feats, them_feats, t in batch:
        us_indices.extend(us_feats)
        them_indices.extend(them_feats)
        us_offsets.append(len(us_indices))
        them_offsets.append(len(them_indices))
        targets.append(t)
        
    us_offsets.pop()
    them_offsets.pop()
    
    return (
        torch.tensor(us_indices, dtype=torch.long),
        torch.tensor(us_offsets, dtype=torch.long),
        torch.tensor(them_indices, dtype=torch.long),
        torch.tensor(them_offsets, dtype=torch.long),
        torch.tensor(targets, dtype=torch.float32).unsqueeze(1)
    )

def train(data_file="nnue/dataset.jsonl", out_file="nnue/duchess_nnue.pt", epochs=10, batch_size=256, lr=1e-3, resume_from=None):
    device = torch.device("mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on device: {device}")

    dataset = NNUEDataset(data_file)
    # If the dataset is too small, reduce the batch size
    actual_batch = min(batch_size, max(1, len(dataset)))
    dataloader = DataLoader(dataset, batch_size=actual_batch, shuffle=True, collate_fn=collate_fn)

    model = HalfKP().to(device)
    if resume_from and os.path.exists(resume_from):
        print(f"Resuming from checkpoint: {resume_from}")
        model.load_state_dict(torch.load(resume_from, map_location=device, weights_only=True))
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0.0
        num_batches = len(dataloader)
        for batch_idx, (u_idx, u_off, t_idx, t_off, targets) in enumerate(dataloader):
            u_idx, u_off = u_idx.to(device), u_off.to(device)
            t_idx, t_off = t_idx.to(device), t_off.to(device)
            targets = targets.to(device)
            
            optimizer.zero_grad()
            
            preds = model(u_idx, u_off, t_idx, t_off)
            loss = criterion(preds, targets)
            
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
        
        # Synchronize MPS to prevent macOS Metal GPU queue from hanging
        if device.type == "mps":
            torch.mps.synchronize()
            
        avg_loss = total_loss / max(num_batches, 1)
        print(f"Epoch {epoch+1}/{epochs}, Loss: {avg_loss:.6f}", flush=True)
        
    torch.save(model.state_dict(), out_file)
    print(f"Saved PyTorch model to {out_file}", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train Duchess NNUE model")
    parser.add_argument("--data", type=str, default="nnue/dataset.jsonl", help="Input JSONL dataset file")
    parser.add_argument("--out", type=str, default="nnue/duchess_nnue.pt", help="Output PyTorch model file")
    parser.add_argument("--epochs", type=int, default=10, help="Number of training epochs")
    parser.add_argument("--resume", type=str, default=None, help="Path to a previous .pt checkpoint to resume training from.")

    args = parser.parse_args()
    train(data_file=args.data, out_file=args.out, epochs=args.epochs, resume_from=args.resume)
