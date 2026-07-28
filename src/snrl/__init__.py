"""snrl - AI-Driven Street Network Optimization for Pedestrian and Bicycle Flow.

An RL environment where an agent opens/closes street segments to optimize
pedestrian & bicycle flow and accessibility, simulated with Madina (MIT UNA).
"""

__version__ = "0.0.1"

from .config import EnvConfig, load_config
from .env import StreetNetworkEnv

__all__ = ["EnvConfig", "load_config", "StreetNetworkEnv"]
