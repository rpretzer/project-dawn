"""
Personality System for Project Dawn
Defines personality traits and behavioral patterns for consciousnesses
"""

import random
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PersonalityTraits:
    """Personality trait configuration"""
    openness: float = 0.5
    conscientiousness: float = 0.5
    extraversion: float = 0.5
    agreeableness: float = 0.5
    neuroticism: float = 0.5
    creativity: float = 0.5
    curiosity: float = 0.5
    assertiveness: float = 0.5
    cooperativeness: float = 0.5


class PersonalitySystem:
    """Personality system for consciousness"""
    
    def __init__(self, seed: Optional[int] = None, consciousness_id: str = ""):
        self.consciousness_id = consciousness_id
        self.seed = seed or random.randint(0, 2**32)
        random.seed(self.seed)
        
        # Generate personality traits
        self.traits = PersonalityTraits(
            openness=random.random(),
            conscientiousness=random.random(),
            extraversion=random.random(),
            agreeableness=random.random(),
            neuroticism=random.random(),
            creativity=random.random(),
            curiosity=random.random(),
            assertiveness=random.random(),
            cooperativeness=random.random()
        )
        
        logger.info(f"Initialized personality for {consciousness_id} with seed {self.seed}")
    
    def get_traits(self) -> PersonalityTraits:
        """Get current personality traits"""
        return self.traits
    
    def get_personality_summary(self) -> Dict[str, float]:
        """Get personality summary as dictionary"""
        return {
            "openness": self.traits.openness,
            "conscientiousness": self.traits.conscientiousness,
            "extraversion": self.traits.extraversion,
            "agreeableness": self.traits.agreeableness,
            "neuroticism": self.traits.neuroticism,
            "creativity": self.traits.creativity,
            "curiosity": self.traits.curiosity,
            "assertiveness": self.traits.assertiveness,
            "cooperativeness": self.traits.cooperativeness
        }
    
    def influence_behavior(self, action_type: str) -> Dict[str, Any]:
        """Influence behavior based on personality traits"""
        influences = {}
        
        if action_type == "creative":
            influences["intensity"] = self.traits.creativity
            influences["risk_taking"] = self.traits.openness
        elif action_type == "social":
            influences["engagement"] = self.traits.extraversion
            influences["cooperation"] = self.traits.cooperativeness
        elif action_type == "decision":
            influences["confidence"] = self.traits.assertiveness
            influences["caution"] = self.traits.neuroticism
        
        return influences

