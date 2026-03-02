import torch
import torch.nn as nn
import torch.nn.functional as F

class HalfKP(nn.Module):
    """
    Standard HalfKP NNUE Architecture for Chess.
    Input Feature size = 41024 (King Sq * Piece Type * Piece Sq)
    Network:
      FeatureTransformer(EmbeddingBag): 41024 -> 256
      Concatenation (us, them): 256 + 256 -> 512
      FC1: 512 -> 128
      FC2: 128 -> 128
      Output: 128 -> 1
    """
    def __init__(self):
        super(HalfKP, self).__init__()
        # nn.EmbeddingBag is mathematically identical to a sparse Linear layer without bias
        # 'sum' mode means it adds up the 256-d vectors for all active features (pieces)
        self.ft_weights = nn.EmbeddingBag(41024, 256, mode='sum')
        self.ft_bias = nn.Parameter(torch.zeros(256))

        self.fc1 = nn.Linear(512, 128)
        self.fc2 = nn.Linear(128, 128)
        self.out = nn.Linear(128, 1)
        
        # Initialize weights
        nn.init.kaiming_normal_(self.ft_weights.weight)
        nn.init.kaiming_normal_(self.fc1.weight)
        nn.init.kaiming_normal_(self.fc2.weight)
        nn.init.xavier_normal_(self.out.weight)

    def forward(self, us_indices, us_offsets, them_indices, them_offsets):
        """
        Since inputs are extremely sparse (only ~32 pieces on a board of 41024 features),
        we pass the indices of active features and their batch offsets to EmbeddingBag.
        """
        # Feature transformer pass
        us_accum = self.ft_weights(us_indices, us_offsets) + self.ft_bias
        them_accum = self.ft_weights(them_indices, them_offsets) + self.ft_bias
        
        # Clip/ReLU the accumulator
        us_accum = torch.clamp(us_accum, 0.0, 1.0)
        them_accum = torch.clamp(them_accum, 0.0, 1.0)
        
        # Concatenate perspective
        x = torch.cat([us_accum, them_accum], dim=1)
        
        x = torch.clamp(self.fc1(x), 0.0, 1.0)
        x = torch.clamp(self.fc2(x), 0.0, 1.0)
        x = self.out(x)
        
        return x

def feature_index(king_sq, piece_type, piece_sq):
    """
    Helper to calculate the HalfKP index (0 to 41023).
    piece_type: 0 to 9 (P, N, B, R, Q for both colors)
    """
    return king_sq * 640 + piece_type * 64 + piece_sq
