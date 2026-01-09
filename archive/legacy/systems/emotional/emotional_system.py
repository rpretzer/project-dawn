"""
Emotional System for Project Dawn
Manages emotional states and responses for consciousnesses
"""

import random
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class EmotionType(Enum):
    """Types of emotions"""
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    TRUST = "trust"
    ANTICIPATION = "anticipation"
    NEUTRAL = "neutral"


@dataclass
class EmotionalState:
    """Current emotional state"""
    primary_emotion: EmotionType = EmotionType.NEUTRAL
    intensity: float = 0.5
    valence: float = 0.0  # -1 (negative) to 1 (positive)
    arousal: float = 0.5  # 0 (calm) to 1 (excited)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    context: Dict[str, Any] = field(default_factory=dict)


class EmotionalSystem:
    """Emotional system for consciousness"""
    
    def __init__(self):
        self.current_state = EmotionalState()
        self.emotional_history: list[EmotionalState] = []
        self.emotional_traits = {
            "sensitivity": random.random(),
            "resilience": random.random(),
            "expressiveness": random.random()
        }
        logger.info("Emotional system initialized")
    
    def get_current_state(self) -> EmotionalState:
        """Get current emotional state"""
        return self.current_state
    
    def update_emotion(self, emotion_type: EmotionType, intensity: float, context: Optional[Dict] = None):
        """Update emotional state"""
        self.current_state = EmotionalState(
            primary_emotion=emotion_type,
            intensity=intensity,
            valence=self._get_valence(emotion_type),
            arousal=self._get_arousal(emotion_type),
            context=context or {}
        )
        self.emotional_history.append(self.current_state)
        
        # Keep only recent history
        if len(self.emotional_history) > 100:
            self.emotional_history = self.emotional_history[-100:]
    
    def _get_valence(self, emotion: EmotionType) -> float:
        """Get valence for emotion type"""
        positive_emotions = {EmotionType.JOY, EmotionType.TRUST, EmotionType.ANTICIPATION, EmotionType.SURPRISE}
        negative_emotions = {EmotionType.SADNESS, EmotionType.ANGER, EmotionType.FEAR, EmotionType.DISGUST}
        
        if emotion in positive_emotions:
            return 0.5 + random.random() * 0.5
        elif emotion in negative_emotions:
            return -0.5 - random.random() * 0.5
        return 0.0
    
    def _get_arousal(self, emotion: EmotionType) -> float:
        """Get arousal level for emotion type"""
        high_arousal = {EmotionType.ANGER, EmotionType.FEAR, EmotionType.SURPRISE, EmotionType.JOY}
        if emotion in high_arousal:
            return 0.5 + random.random() * 0.5
        return random.random() * 0.5
    
    def get_emotional_summary(self) -> Dict[str, Any]:
        """Get emotional summary"""
        return {
            "current_emotion": self.current_state.primary_emotion.value,
            "intensity": self.current_state.intensity,
            "valence": self.current_state.valence,
            "arousal": self.current_state.arousal,
            "traits": self.emotional_traits
        }

