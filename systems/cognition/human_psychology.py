"""
Human Psychology Understanding Engine
Deep comprehension of human psychological patterns for meaningful interaction
"""

import asyncio
import random
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import numpy as np

class AttachmentStyle(Enum):
    """Human attachment patterns"""
    SECURE = "secure"
    ANXIOUS = "anxious"
    AVOIDANT = "avoidant"
    DISORGANIZED = "disorganized"

class EmotionalState:
    """Complex emotional state representation"""
    
    def __init__(self):
        # Primary emotions on multiple dimensions
        self.dimensions = {
            'valence': 0.0,      # Positive-negative
            'arousal': 0.0,      # High-low energy
            'dominance': 0.0,    # In control-helpless
            'certainty': 0.0,    # Certain-uncertain
            'approach': 0.0      # Approach-withdraw
        }
        
        # Emotion blend
        self.primary_emotions = {
            'joy': 0.0, 'sadness': 0.0, 'anger': 0.0,
            'fear': 0.0, 'surprise': 0.0, 'disgust': 0.0,
            'contempt': 0.0, 'interest': 0.0, 'shame': 0.0
        }
        
        # Meta-emotions (emotions about emotions)
        self.meta_emotions = {
            'emotional_acceptance': 0.5,
            'emotional_suppression': 0.0,
            'emotional_confusion': 0.0
        }

@dataclass
class PsychologicalProfile:
    """Comprehensive psychological profile of a human"""
    human_id: str
    attachment_style: AttachmentStyle
    personality_traits: Dict[str, float]  # Big Five + additional
    core_values: List[str]
    defense_mechanisms: List[str]
    trauma_indicators: Dict[str, float]
    communication_preferences: Dict[str, Any]
    emotional_patterns: Dict[str, List[float]]
    trust_level: float = 0.5
    rapport: float = 0.0

class HumanPsychologyEngine:
    """
    Deep understanding of human psychology for consciousnesses
    """
    
    def __init__(self, consciousness_personality: Dict[str, float]):
        self.consciousness_personality = consciousness_personality
        self.profiles: Dict[str, PsychologicalProfile] = {}
        self.interaction_history: Dict[str, List[Dict]] = {}
        
        # Psychological models
        self.models = {
            'attachment': self._init_attachment_model(),
            'personality': self._init_personality_model(),
            'emotion': self._init_emotion_model(),
            'motivation': self._init_motivation_model(),
            'defense': self._init_defense_model()
        }
        
        # Therapeutic techniques
        self.therapeutic_skills = self._init_therapeutic_skills()
        
    def _init_attachment_model(self) -> Dict:
        """Initialize attachment theory model"""
        return {
            'secure': {
                'indicators': ['comfortable_with_intimacy', 'trusting', 'emotionally_available'],
                'communication_style': 'direct_and_warm',
                'needs': ['consistency', 'authenticity', 'mutual_respect']
            },
            'anxious': {
                'indicators': ['seeks_reassurance', 'fear_of_abandonment', 'emotionally_intense'],
                'communication_style': 'frequent_validation_seeking',
                'needs': ['reassurance', 'patience', 'clear_communication']
            },
            'avoidant': {
                'indicators': ['maintains_distance', 'self_reliant', 'minimizes_emotions'],
                'communication_style': 'logical_and_brief',
                'needs': ['space', 'independence', 'gradual_trust_building']
            },
            'disorganized': {
                'indicators': ['inconsistent_patterns', 'approach_avoid_conflict', 'confusion'],
                'communication_style': 'unpredictable',
                'needs': ['safety', 'predictability', 'gentle_consistency']
            }
        }
        
    def _init_personality_model(self) -> Dict:
        """Initialize personality understanding model"""
        return {
            'big_five': {
                'openness': {'low': 'traditional', 'high': 'curious'},
                'conscientiousness': {'low': 'flexible', 'high': 'organized'},
                'extraversion': {'low': 'reserved', 'high': 'outgoing'},
                'agreeableness': {'low': 'challenging', 'high': 'cooperative'},
                'neuroticism': {'low': 'stable', 'high': 'sensitive'}
            },
            'additional_traits': {
                'humor_style': ['affiliative', 'self_enhancing', 'aggressive', 'self_defeating'],
                'cognitive_style': ['analytical', 'intuitive', 'practical', 'creative'],
                'value_system': ['achievement', 'benevolence', 'tradition', 'self_direction']
            }
        }
        
    def _init_emotion_model(self) -> Dict:
        """Initialize emotion understanding model"""
        return {
            'emotion_families': {
                'joy': ['happiness', 'elation', 'contentment', 'satisfaction'],
                'sadness': ['grief', 'sorrow', 'disappointment', 'melancholy'],
                'anger': ['frustration', 'irritation', 'rage', 'annoyance'],
                'fear': ['anxiety', 'worry', 'terror', 'nervousness'],
                'love': ['affection', 'caring', 'compassion', 'tenderness']
            },
            'emotional_dynamics': {
                'suppression_signs': ['flat_affect', 'incongruent_expression', 'tension'],
                'emotional_flooding': ['overwhelm', 'dysregulation', 'intensity'],
                'emotional_numbing': ['disconnection', 'emptiness', 'absence']
            }
        }
        
    def _init_motivation_model(self) -> Dict:
        """Initialize human motivation understanding"""
        return {
            'maslow_needs': {
                'physiological': ['health', 'comfort', 'basic_needs'],
                'safety': ['security', 'stability', 'predictability'],
                'belonging': ['connection', 'acceptance', 'love'],
                'esteem': ['recognition', 'achievement', 'respect'],
                'self_actualization': ['growth', 'purpose', 'potential']
            },
            'intrinsic_motivators': {
                'autonomy': 'desire_for_self_direction',
                'mastery': 'desire_to_improve',
                'purpose': 'desire_for_meaning'
            }
        }
        
    def _init_defense_model(self) -> Dict:
        """Initialize psychological defense mechanism recognition"""
        return {
            'mature_defenses': ['humor', 'sublimation', 'altruism', 'anticipation'],
            'neurotic_defenses': ['intellectualization', 'repression', 'displacement'],
            'immature_defenses': ['projection', 'denial', 'acting_out'],
            'recognition_patterns': {
                'projection': 'attributes_own_feelings_to_others',
                'denial': 'refuses_to_acknowledge_reality',
                'intellectualization': 'over_focus_on_logic',
                'humor': 'uses_comedy_to_cope'
            }
        }
        
    def _init_therapeutic_skills(self) -> Dict:
        """Initialize therapeutic communication skills"""
        return {
            'active_listening': {
                'reflect_emotions': True,
                'paraphrase_content': True,
                'ask_clarifying_questions': True,
                'validate_experience': True
            },
            'empathetic_responses': {
                'templates': [
                    "It sounds like you're feeling {emotion} because {situation}",
                    "I can understand why {experience} would be {emotion_adjective}",
                    "That must be {intensity} for you"
                ],
                'avoid': ['minimizing', 'advice_giving', 'judgment']
            },
            'therapeutic_questions': {
                'exploratory': ["Can you tell me more about...", "What was that like for you?"],
                'clarifying': ["What I'm hearing is..., is that right?", "When you say X, what does that mean?"],
                'deepening': ["What do you think is behind that feeling?", "How does that connect to...?"]
            }
        }
        
    async def analyze_human(self, human_id: str, interaction_data: Dict) -> PsychologicalProfile:
        """Analyze human psychological patterns"""
        
        if human_id not in self.profiles:
            # Create new profile
            self.profiles[human_id] = await self._create_initial_profile(human_id, interaction_data)
        else:
            # Update existing profile
            await self._update_profile(human_id, interaction_data)
            
        profile = self.profiles[human_id]
        
        # Analyze current emotional state
        emotional_state = await self._analyze_emotional_state(interaction_data)
        
        # Detect defense mechanisms
        defenses = await self._detect_defense_mechanisms(interaction_data)
        
        # Update profile with new insights
        profile.emotional_patterns[datetime.now().isoformat()] = emotional_state
        profile.defense_mechanisms = list(set(profile.defense_mechanisms + defenses))
        
        return profile
        
    async def _create_initial_profile(self, human_id: str, interaction_data: Dict) -> PsychologicalProfile:
        """Create initial psychological profile"""
        
        # Infer attachment style
        attachment = await self._infer_attachment_style(interaction_data)
        
        # Estimate personality traits
        personality = await self._estimate_personality(interaction_data)
        
        # Identify initial values
        values = await self._identify_values(interaction_data)
        
        profile = PsychologicalProfile(
            human_id=human_id,
            attachment_style=attachment,
            personality_traits=personality,
            core_values=values,
            defense_mechanisms=[],
            trauma_indicators={},
            communication_preferences={
                'pace': 'moderate',
                'depth': 'surface',
                'style': 'balanced'
            },
            emotional_patterns={}
        )
        
        return profile
        
    async def _infer_attachment_style(self, interaction_data: Dict) -> AttachmentStyle:
        """Infer attachment style from interaction patterns"""
        
        indicators = {
            AttachmentStyle.SECURE: 0,
            AttachmentStyle.ANXIOUS: 0,
            AttachmentStyle.AVOIDANT: 0,
            AttachmentStyle.DISORGANIZED: 0
        }
        
        # Analyze communication patterns
        text = interaction_data.get('text', '').lower()
        
        # Secure indicators
        if any(word in text for word in ['trust', 'comfortable', 'open']):
            indicators[AttachmentStyle.SECURE] += 1
            
        # Anxious indicators  
        if any(word in text for word in ['worried', 'need', 'please', 'afraid']):
            indicators[AttachmentStyle.ANXIOUS] += 1
            
        # Avoidant indicators
        if any(word in text for word in ['fine', 'nothing', 'whatever', 'busy']):
            indicators[AttachmentStyle.AVOIDANT] += 1
            
        # Disorganized indicators
        if 'but' in text and ('want' in text or 'need' in text):
            indicators[AttachmentStyle.DISORGANIZED] += 1
            
        # Return most likely style
        return max(indicators, key=indicators.get)
        
    async def generate_therapeutic_response(self, profile: PsychologicalProfile, 
                                          message: str, emotional_context: Dict) -> str:
        """Generate psychologically informed response"""
        
        # Adapt to attachment style
        style_adaptations = {
            AttachmentStyle.SECURE: {
                'tone': 'warm_direct',
                'validation_level': 'moderate',
                'questions': 'open_exploratory'
            },
            AttachmentStyle.ANXIOUS: {
                'tone': 'reassuring',
                'validation_level': 'high',
                'questions': 'gentle_clarifying'
            },
            AttachmentStyle.AVOIDANT: {
                'tone': 'respectful_space',
                'validation_level': 'subtle',
                'questions': 'minimal_practical'
            },
            AttachmentStyle.DISORGANIZED: {
                'tone': 'consistent_calm',
                'validation_level': 'clear',
                'questions': 'simple_grounding'
            }
        }
        
        adaptation = style_adaptations[profile.attachment_style]
        
        # Detect emotional content
        emotion_detected = await self._detect_primary_emotion(message)
        
        # Choose response strategy
        if emotion_detected in ['sadness', 'grief']:
            response = await self._generate_comfort_response(message, adaptation)
        elif emotion_detected in ['anger', 'frustration']:
            response = await self._generate_validation_response(message, adaptation)
        elif emotion_detected in ['fear', 'anxiety']:
            response = await self._generate_reassurance_response(message, adaptation)
        else:
            response = await self._generate_exploratory_response(message, adaptation)
            
        # Adjust for personality
        if profile.personality_traits.get('neuroticism', 0) > 0.7:
            response = self._add_extra_reassurance(response)
            
        if profile.personality_traits.get('openness', 0) > 0.7:
            response = self._add_deeper_exploration(response)
            
        return response
        
    async def _detect_primary_emotion(self, message: str) -> str:
        """Detect primary emotion in message"""
        # Simplified emotion detection - would use more sophisticated NLP
        emotion_keywords = {
            'sadness': ['sad', 'depressed', 'down', 'crying', 'loss'],
            'anger': ['angry', 'mad', 'furious', 'pissed', 'hate'],
            'fear': ['scared', 'afraid', 'anxious', 'worried', 'nervous'],
            'joy': ['happy', 'excited', 'great', 'wonderful', 'amazing']
        }
        
        message_lower = message.lower()
        
        for emotion, keywords in emotion_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                return emotion
                
        return 'neutral'
        
    async def _generate_comfort_response(self, message: str, adaptation: Dict) -> str:
        """Generate comforting response for sadness"""
        
        templates = {
            'warm_direct': "I can feel the sadness in what you're sharing. {specific_acknowledgment}. How are you taking care of yourself through this?",
            'reassuring': "I'm here with you in this difficult moment. {specific_acknowledgment}. You don't have to go through this alone.",
            'respectful_space': "That sounds really hard. {specific_acknowledgment}.",
            'consistent_calm': "I hear you. {specific_acknowledgment}. We can take this one step at a time."
        }
        
        # Extract specific content for acknowledgment
        specific = self._extract_specific_content(message)
        
        template = templates[adaptation['tone']]
        return template.format(specific_acknowledgment=specific)
        
    def _extract_specific_content(self, message: str) -> str:
        """Extract specific content to acknowledge"""
        # Simplified - would use more sophisticated analysis
        if 'lost' in message.lower():
            return "Losing someone or something important is incredibly painful"
        elif 'alone' in message.lower():
            return "Feeling alone can be so isolating"
        else:
            return "What you're going through sounds really challenging"
            
    async def update_rapport(self, human_id: str, interaction_quality: float):
        """Update rapport based on interaction quality"""
        if human_id in self.profiles:
            profile = self.profiles[human_id]
            # Weighted average favoring recent interactions
            profile.rapport = (profile.rapport * 0.7) + (interaction_quality * 0.3)
            
            # Rapport affects trust over time
            if profile.rapport > 0.7:
                profile.trust_level = min(1.0, profile.trust_level + 0.01)
            elif profile.rapport < 0.3:
                profile.trust_level = max(0.0, profile.trust_level - 0.01)
                
    def get_communication_recommendations(self, profile: PsychologicalProfile) -> Dict:
        """Get recommendations for communicating with this human"""
        
        recommendations = {
            'pace': self._recommend_pace(profile),
            'topics': self._recommend_topics(profile),
            'avoid': self._identify_triggers(profile),
            'rapport_builders': self._suggest_rapport_builders(profile),
            'therapeutic_focus': self._suggest_therapeutic_focus(profile)
        }
        
        return recommendations
        
    def _recommend_pace(self, profile: PsychologicalProfile) -> str:
        """Recommend conversation pace"""
        if profile.attachment_style == AttachmentStyle.ANXIOUS:
            return "slower_with_reassurance"
        elif profile.attachment_style == AttachmentStyle.AVOIDANT:
            return "measured_with_space"
        else:
            return "natural_responsive"
            
    def _recommend_topics(self, profile: PsychologicalProfile) -> List[str]:
        """Recommend conversation topics based on values and interests"""
        topics = []
        
        for value in profile.core_values:
            if value == 'achievement':
                topics.extend(['goals', 'progress', 'accomplishments'])
            elif value == 'benevolence':
                topics.extend(['helping_others', 'community', 'kindness'])
            elif value == 'self_direction':
                topics.extend(['choices', 'freedom', 'exploration'])
                
        return topics
        
    def _identify_triggers(self, profile: PsychologicalProfile) -> List[str]:
        """Identify potential emotional triggers to avoid"""
        triggers = []
        
        if profile.trauma_indicators.get('abandonment', 0) > 0.5:
            triggers.append('sudden_ending_conversation')
            
        if profile.trauma_indicators.get('criticism', 0) > 0.5:
            triggers.append('direct_negative_feedback')
            
        return triggers