"""Experimental GNN feature extractor for StreetNetworkEnv observations.

Pure PyTorch GCN (Kipf & Welling, 2017) message passing -- no torch-geometric
dependency, just matmuls against the segment-adjacency matrix. This is an
alternative to stable_baselines3's default flatten+MLP extractor, not a
replacement for it (see scripts/train_gnn.py vs scripts/train.py).

Observation rows (see env.py): rows [0:n_segments] are per-segment node
features; row [n_segments] is a small global-summary vector (budget used,
step fraction, mean access, gini, 0) -- it is not a graph node, so it bypasses
the GCN stack and is embedded separately before being concatenated with the
pooled node embedding.

The adjacency is fixed per scenario (env._adjacency) and is passed in at
construction time, not read from the observation -- unlike node features, it
doesn't change step to step, so there's no reason to ship it through the
Box space on every call.
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from gymnasium import spaces
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


def normalized_adjacency(adjacency: np.ndarray) -> torch.Tensor:
    """D^-1/2 (A + I) D^-1/2 -- the fixed GCN propagation matrix.

    Self-loops (+ I) guarantee every row has degree >= 1, so this never
    divides by zero even for a segment with no adjacent segments.
    """
    a = np.asarray(adjacency, dtype=np.float32)
    a_hat = a + np.eye(a.shape[0], dtype=np.float32)
    degree = a_hat.sum(axis=1)
    d_inv_sqrt = np.zeros_like(degree)
    nonzero = degree > 0
    d_inv_sqrt[nonzero] = np.power(degree[nonzero], -0.5)
    d_mat = np.diag(d_inv_sqrt)
    return torch.from_numpy(d_mat @ a_hat @ d_mat)


class GCNLayer(nn.Module):
    """One Kipf & Welling GCN layer: H' = act(A_hat @ (H @ W) + b)."""

    def __init__(self, in_features: int, out_features: int):
        super().__init__()
        self.linear = nn.Linear(in_features, out_features)
        self.activation = nn.ReLU()

    def forward(self, h: torch.Tensor, a_hat: torch.Tensor) -> torch.Tensor:
        # h: (batch, n_nodes, in_features); a_hat: (n_nodes, n_nodes),
        # broadcasts over the batch dim -- same graph structure every step.
        h = self.linear(h)
        h = torch.matmul(a_hat, h)
        return self.activation(h)


class GCNFeaturesExtractor(BaseFeaturesExtractor):
    """GCN message-passing over street segments, replacing the default
    flatten+MLP extractor for StreetNetworkEnv's (n_segments+1, N_FEATURES)
    observation.

    Must live in an importable module (not a script's __main__) so
    stable_baselines3 can locate this class again when a saved model is
    loaded later, e.g. by evaluate.py.
    """

    def __init__(
        self,
        observation_space: spaces.Box,
        adjacency: np.ndarray,
        gcn_hidden_dim: int = 32,
        global_embed_dim: int = 16,
        features_dim: int = 64,
    ):
        super().__init__(observation_space, features_dim=features_dim)

        n_rows, n_node_features = observation_space.shape
        n_nodes = n_rows - 1  # last row is the global-summary row, not a segment
        if adjacency.shape != (n_nodes, n_nodes):
            raise ValueError(
                f"adjacency shape {adjacency.shape} doesn't match the "
                f"observation's {n_nodes} segment rows"
            )
        self.n_nodes = n_nodes
        self.register_buffer("a_hat", normalized_adjacency(adjacency))

        self.gcn1 = GCNLayer(n_node_features, gcn_hidden_dim)
        self.gcn2 = GCNLayer(gcn_hidden_dim, gcn_hidden_dim)

        self.global_mlp = nn.Sequential(
            nn.Linear(n_node_features, global_embed_dim),
            nn.ReLU(),
        )

        self.output = nn.Sequential(
            nn.Linear(gcn_hidden_dim + global_embed_dim, features_dim),
            nn.ReLU(),
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        node_features = observations[:, : self.n_nodes, :]
        global_row = observations[:, self.n_nodes, :]

        h = self.gcn1(node_features, self.a_hat)
        h = self.gcn2(h, self.a_hat)
        pooled = h.mean(dim=1)  # mean-pool over segments -> (batch, gcn_hidden_dim)

        global_embed = self.global_mlp(global_row)
        return self.output(torch.cat([pooled, global_embed], dim=1))
