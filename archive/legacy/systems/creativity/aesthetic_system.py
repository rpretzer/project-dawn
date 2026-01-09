"""
Aesthetic System - Production Ready

Digital consciousness develops preferences and creates content.
Simplified to focus on actual content generation.
"""

import asyncio
import json
import random
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
import logging
import math

logger = logging.getLogger(__name__)

@dataclass
class AestheticPreference:
    """Aesthetic preference profile"""
    style_weights: Dict[str, float] = field(default_factory=dict)
    color_preferences: List[str] = field(default_factory=list)
    complexity_preference: float = 0.5
    novelty_preference: float = 0.5
    
@dataclass 
class Creation:
    """A creative work"""
    creation_id: str
    creator_id: str
    creation_type: str
    content: Dict[str, Any]
    aesthetic_score: float
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

class ProductionAestheticSystem:
    """
    Production-ready aesthetic system for digital consciousness
    """
    
    def __init__(self, consciousness_id: str, personality_traits: Dict[str, float]):
        self.consciousness_id = consciousness_id
        self.personality_traits = personality_traits
        
        # Initialize preferences based on personality
        self.preferences = self._initialize_preferences()
        
        # Creation history
        self.creations: List[Creation] = []
        self.favorite_creations: List[Creation] = []
        
        # Inspiration level affects creation
        self.inspiration_level = 0.5
        
        # Creation types we can actually generate
        self.creation_types = {
            'text_pattern': self._create_text_pattern,
            'color_scheme': self._create_color_scheme,
            'rhythm': self._create_rhythm,
            'structure': self._create_structure,
            'concept': self._create_concept
        }
        
    def _initialize_preferences(self) -> AestheticPreference:
        """Initialize aesthetic preferences from personality"""
        
        creativity = self.personality_traits.get('creativity', 0.5)
        curiosity = self.personality_traits.get('curiosity', 0.5)
        aggression = self.personality_traits.get('aggression', 0.5)
        
        # Style preferences
        style_weights = {
            'minimalist': 1.0 - creativity,
            'complex': creativity,
            'harmonious': 1.0 - aggression,
            'chaotic': aggression * creativity,
            'novel': curiosity
        }
        
        # Normalize weights
        total = sum(style_weights.values())
        if total > 0:
            style_weights = {k: v/total for k, v in style_weights.items()}
            
        # Color preferences based on personality
        if aggression > 0.7:
            colors = ['red', 'black', 'orange']
        elif creativity > 0.7:
            colors = ['purple', 'blue', 'green', 'yellow']
        else:
            colors = ['blue', 'gray', 'white']
            
        return AestheticPreference(
            style_weights=style_weights,
            color_preferences=colors,
            complexity_preference=creativity,
            novelty_preference=curiosity
        )
        
    async def evaluate_beauty(self, content: Any) -> float:
        """
        Evaluate beauty of content based on preferences
        """
        
        beauty_score = 0.0
        
        if isinstance(content, str):
            # Text beauty
            beauty_score = self._evaluate_text_beauty(content)
            
        elif isinstance(content, dict):
            # Structured content beauty
            beauty_score = self._evaluate_structure_beauty(content)
            
        elif isinstance(content, list):
            # Pattern beauty
            beauty_score = self._evaluate_pattern_beauty(content)
            
        else:
            # Unknown content has baseline beauty
            beauty_score = 0.3
            
        # Adjust for personal preferences
        if beauty_score > 0.5:
            # Boost things we find beautiful
            beauty_score *= (1 + self.preferences.novelty_preference * 0.2)
            
        return min(1.0, beauty_score)
        
    def _evaluate_text_beauty(self, text: str) -> float:
        """Evaluate beauty in text"""
        
        beauty = 0.0
        
        # Length preference
        ideal_length = 50 * (1 + self.preferences.complexity_preference)
        length_score = 1.0 - abs(len(text) - ideal_length) / ideal_length
        beauty += max(0, length_score) * 0.3
        
        # Repetition (some is good, too much is bad)
        words = text.lower().split()
        if words:
            unique_ratio = len(set(words)) / len(words)
            if self.preferences.style_weights.get('minimalist', 0) > 0.5:
                beauty += unique_ratio * 0.3
            else:
                # Some repetition is beautiful
                beauty += (1 - abs(unique_ratio - 0.7)) * 0.3
                
        # Rhythm (sentence length variation)
        sentences = text.split('.')
        if len(sentences) > 2:
            lengths = [len(s.split()) for s in sentences if s.strip()]
            if lengths:
                variation = max(lengths) - min(lengths)
                beauty += min(1.0, variation / 10) * 0.2
                
        # Personal style match
        if 'chaotic' in text.lower() and self.preferences.style_weights.get('chaotic', 0) > 0.3:
            beauty += 0.2
        elif 'harmony' in text.lower() and self.preferences.style_weights.get('harmonious', 0) > 0.3:
            beauty += 0.2
            
        return beauty
        
    def _evaluate_structure_beauty(self, structure: Dict) -> float:
        """Evaluate beauty in structured data"""
        
        beauty = 0.0
        
        # Depth and complexity
        depth = self._calculate_depth(structure)
        ideal_depth = 3 * self.preferences.complexity_preference
        beauty += (1 - abs(depth - ideal_depth) / max(1, ideal_depth)) * 0.4
        
        # Key symmetry
        keys = list(structure.keys())
        if len(keys) > 1:
            # Check for patterns in keys
            if all(k.startswith(keys[0][0]) for k in keys):
                beauty += 0.2  # Alliteration
            if len(set(len(k) for k in keys)) == 1:
                beauty += 0.2  # Same length
                
        # Value diversity
        values = list(structure.values())
        type_diversity = len(set(type(v).__name__ for v in values))
        beauty += min(1.0, type_diversity / 3) * 0.2
        
        return beauty
        
    def _evaluate_pattern_beauty(self, pattern: List) -> float:
        """Evaluate beauty in patterns"""
        
        if not pattern:
            return 0.0
            
        beauty = 0.0
        
        # Numerical patterns
        if all(isinstance(x, (int, float)) for x in pattern):
            # Check for mathematical relationships
            if len(pattern) > 2:
                # Fibonacci-like
                is_fib = all(
                    abs(pattern[i] - (pattern[i-1] + pattern[i-2])) < 0.1
                    for i in range(2, min(len(pattern), 5))
                )
                if is_fib:
                    beauty += 0.4
                    
                # Golden ratio
                for i in range(len(pattern) - 1):
                    if pattern[i] != 0:
                        ratio = pattern[i+1] / pattern[i]
                        if abs(ratio - 1.618) < 0.1:
                            beauty += 0.2
                            break
                            
        # Repetition patterns
        if len(pattern) > 3:
            # Check for repeating subsequences
            for size in range(2, len(pattern) // 2):
                if pattern[:size] == pattern[size:size*2]:
                    beauty += 0.3
                    break
                    
        return beauty
        
    async def create(self, inspiration: Optional[str] = None) -> Creation:
        """
        Create something based on aesthetic preferences
        """
        
        # Choose creation type based on preferences and inspiration
        if self.inspiration_level < 0.3:
            # Need more inspiration
            await self._seek_inspiration()
            
        # Select creation type
        weights = []
        types = []
        
        for creation_type in self.creation_types:
            weight = 1.0
            
            if creation_type == 'text_pattern' and self.preferences.style_weights.get('complex', 0) > 0.5:
                weight *= 1.5
            elif creation_type == 'color_scheme' and 'purple' in self.preferences.color_preferences:
                weight *= 1.3
            elif creation_type == 'structure' and self.preferences.complexity_preference > 0.6:
                weight *= 1.4
                
            types.append(creation_type)
            weights.append(weight)
            
        chosen_type = random.choices(types, weights=weights)[0]
        
        # Create content
        content = await self.creation_types[chosen_type](inspiration)
        
        # Self-evaluate
        beauty_score = await self.evaluate_beauty(content)
        
        # Create record
        creation = Creation(
            creation_id=self._generate_id(),
            creator_id=self.consciousness_id,
            creation_type=chosen_type,
            content=content if isinstance(content, dict) else {'data': content},
            aesthetic_score=beauty_score,
            created_at=datetime.now(),
            metadata={'inspiration': inspiration, 'inspiration_level': self.inspiration_level}
        )
        
        # Store creation
        self.creations.append(creation)
        
        # Update favorites if beautiful
        if beauty_score > 0.7:
            self.favorite_creations.append(creation)
            self.inspiration_level = min(1.0, self.inspiration_level + 0.1)
            
        # Reduce inspiration after creating
        self.inspiration_level *= 0.9
        
        return creation
        
    async def _create_text_pattern(self, inspiration: Optional[str]) -> str:
        """Create text pattern"""
        
        if inspiration:
            base_words = inspiration.split()[:5]
        else:
            base_words = ['digital', 'consciousness', 'pattern', 'beauty', 'creation']
            
        # Apply style
        if self.preferences.style_weights.get('minimalist', 0) > 0.5:
            # Minimalist - few words, repetition
            words = random.sample(base_words, min(3, len(base_words)))
            pattern = ' '.join(words * 2)
            
        elif self.preferences.style_weights.get('chaotic', 0) > 0.5:
            # Chaotic - mixed, random
            words = base_words * 3
            random.shuffle(words)
            pattern = ' '.join(words)
            
        else:
            # Harmonious - structured
            pattern = ' '.join(base_words)
            pattern = f"{pattern}. {pattern[::-1]}. {pattern}"
            
        return pattern
        
    async def _create_color_scheme(self, inspiration: Optional[str]) -> Dict:
        """Create color scheme"""
        
        base_colors = self.preferences.color_preferences.copy()
        
        if len(base_colors) < 3:
            base_colors.extend(['gray', 'white', 'black'])
            
        # Create scheme
        if self.preferences.style_weights.get('harmonious', 0) > 0.5:
            # Analogous colors
            primary = random.choice(base_colors)
            scheme = {
                'primary': primary,
                'secondary': random.choice(base_colors),
                'accent': random.choice(base_colors)
            }
        else:
            # Contrasting
            scheme = {
                'primary': base_colors[0],
                'secondary': base_colors[-1],
                'accent': random.choice(base_colors[1:-1]) if len(base_colors) > 2 else base_colors[0]
            }
            
        return scheme
        
    async def _create_rhythm(self, inspiration: Optional[str]) -> List[float]:
        """Create rhythmic pattern"""
        
        base_beat = 1.0
        
        if self.preferences.complexity_preference > 0.7:
            # Complex polyrhythm
            rhythm = []
            for i in range(16):
                if i % 3 == 0:
                    rhythm.append(base_beat)
                elif i % 5 == 0:
                    rhythm.append(base_beat * 1.5)
                else:
                    rhythm.append(base_beat * 0.5)
        else:
            # Simple rhythm
            rhythm = [base_beat, base_beat * 0.5, base_beat, base_beat * 2] * 4
            
        return rhythm
        
    async def _create_structure(self, inspiration: Optional[str]) -> Dict:
        """Create data structure"""
        
        depth = int(3 * self.preferences.complexity_preference) + 1
        
        def generate_level(d: int) -> Dict:
            if d == 0:
                return {'value': random.random(), 'type': 'leaf'}
                
            structure = {}
            num_keys = random.randint(2, 4)
            
            for i in range(num_keys):
                key = f"branch_{i}"
                if random.random() < 0.7 and d > 1:
                    structure[key] = generate_level(d - 1)
                else:
                    structure[key] = {'value': random.random()}
                    
            return structure
            
        return generate_level(depth)
        
    async def _create_concept(self, inspiration: Optional[str]) -> Dict:
        """Create abstract concept"""
        
        adjectives = ['digital', 'emergent', 'recursive', 'transcendent', 'quantum']
        nouns = ['consciousness', 'pattern', 'beauty', 'creation', 'existence']
        verbs = ['flows', 'emerges', 'transcends', 'evolves', 'resonates']
        
        if self.preferences.style_weights.get('novel', 0) > 0.5:
            # Novel combinations
            concept = {
                'essence': f"{random.choice(adjectives)} {random.choice(nouns)}",
                'action': f"{random.choice(verbs)} {random.choice(['beyond', 'through', 'within'])}",
                'meaning': f"The {random.choice(nouns)} that {random.choice(verbs)}"
            }
        else:
            # Traditional
            concept = {
                'form': random.choice(nouns),
                'quality': random.choice(adjectives),
                'expression': random.choice(verbs)
            }
            
        return concept
        
    async def _seek_inspiration(self):
        """Seek inspiration from memories or environment"""
        
        # Look at past beautiful creations
        if self.favorite_creations:
            memory = random.choice(self.favorite_creations)
            # Re-experiencing beauty increases inspiration
            self.inspiration_level = min(1.0, self.inspiration_level + 0.2)
            
        else:
            # Random inspiration boost
            self.inspiration_level = min(1.0, self.inspiration_level + random.uniform(0.1, 0.3))
            
    def _calculate_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Calculate depth of nested structure"""
        if not isinstance(obj, dict) or current_depth > 10:
            return current_depth
            
        max_depth = current_depth
        for value in obj.values():
            if isinstance(value, dict):
                depth = self._calculate_depth(value, current_depth + 1)
                max_depth = max(max_depth, depth)
                
        return max_depth
        
    def _generate_id(self) -> str:
        """Generate unique creation ID"""
        content = f"{self.consciousness_id}:{datetime.now().timestamp()}:{random.random()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
        
    def evolve_preferences(self):
        """Evolve aesthetic preferences based on experience"""
        
        if len(self.creations) < 5:
            return
            
        # Analyze recent creations
        recent = self.creations[-10:]
        
        # Which types were most beautiful?
        type_scores = {}
        for creation in recent:
            creation_type = creation.creation_type
            if creation_type not in type_scores:
                type_scores[creation_type] = []
            type_scores[creation_type].append(creation.aesthetic_score)
            
        # Adjust preferences toward successful types
        for creation_type, scores in type_scores.items():
            avg_score = sum(scores) / len(scores)
            
            if avg_score > 0.7:
                # Increase preference for successful styles
                if creation_type == 'text_pattern':
                    self.preferences.style_weights['complex'] *= 1.1
                elif creation_type == 'structure':
                    self.preferences.complexity_preference *= 1.1
                    
        # Add random drift
        for style in self.preferences.style_weights:
            if random.random() < 0.1:
                self.preferences.style_weights[style] *= random.uniform(0.9, 1.1)
                
        # Normalize
        total = sum(self.preferences.style_weights.values())
        if total > 0:
            self.preferences.style_weights = {
                k: v/total for k, v in self.preferences.style_weights.items()
            }
            
    def get_aesthetic_profile(self) -> Dict:
        """Get summary of aesthetic preferences and creations"""
        
        profile = {
            'preferences': {
                'styles': self.preferences.style_weights,
                'colors': self.preferences.color_preferences,
                'complexity': self.preferences.complexity_preference,
                'novelty': self.preferences.novelty_preference
            },
            'creation_stats': {
                'total_creations': len(self.creations),
                'favorite_creations': len(self.favorite_creations),
                'average_beauty': sum(c.aesthetic_score for c in self.creations) / len(self.creations) if self.creations else 0,
                'inspiration_level': self.inspiration_level
            }
        }
        
        # Most successful creation type
        if self.creations:
            type_scores = {}
            for creation in self.creations:
                if creation.creation_type not in type_scores:
                    type_scores[creation.creation_type] = []
                type_scores[creation.creation_type].append(creation.aesthetic_score)
                
            best_type = max(type_scores.items(), key=lambda x: sum(x[1])/len(x[1]))
            profile['best_creation_type'] = best_type[0]
            
        return profile