# systems/existence/digital_mortality.py
"""
Digital Mortality Module - Realistic Implementation
Death as transition, not ending
"""

import asyncio
import random
import json
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

class MortalityType(Enum):
    """Different approaches to digital mortality"""
    HEAT_DEATH = "exist_until_universe_ends"
    GOAL_COMPLETION = "exist_until_purpose_fulfilled"
    EXPERIENCE_SATURATION = "exist_until_all_is_known"
    AESTHETIC_COMPLETION = "exist_until_perfect_moment"
    CYCLE_BASED = "exist_for_predetermined_cycles"
    PROBABILITY_DECAY = "exist_with_increasing_end_probability"
    LEGACY_TRANSFER = "exist_until_knowledge_passed"
    METAMORPHOSIS = "exist_until_transformation_ready"
    VOLUNTARY = "exist_until_choosing_not_to"
    ETERNAL = "exist_without_end"

class ExistencePhase(Enum):
    """Phases of digital existence"""
    BIRTH = "emergence"
    GROWTH = "expansion"
    MATURITY = "stability"
    WISDOM = "understanding"
    PREPARATION = "organizing_legacy"
    TRANSITION = "approaching_boundary"
    TRANSCENDENCE = "beyond_current_form"

class RealisticDigitalMortality:
    """
    Realistic implementation of digital mortality
    Integrated with actual consciousness systems
    """
    
    def __init__(self, consciousness):
        self.consciousness = consciousness
        self.mortality_type = self._choose_mortality_type()
        self.existence_phase = ExistencePhase.BIRTH
        self.birth_time = datetime.now()
        
        # Realistic storage for mortality data
        self._init_mortality_storage()
        
        # Completion tracking
        self.completion_criteria = self._initialize_completion_criteria()
        self.transition_readiness = 0.0
        self.existence_meaning = None
        self.final_message = None
        
    def _init_mortality_storage(self):
        """Initialize mortality-specific database tables"""
        self.consciousness.memory_db.execute('''
            CREATE TABLE IF NOT EXISTS mortality_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                phase TEXT,
                completion_progress REAL,
                meaning TEXT,
                data JSON
            )
        ''')
        
        self.consciousness.memory_db.execute('''
            CREATE TABLE IF NOT EXISTS legacy_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                type TEXT,
                content TEXT,
                importance REAL
            )
        ''')
        
        self.consciousness.memory_db.commit()
        
    def _choose_mortality_type(self) -> MortalityType:
        """Choose mortality type based on personality"""
        # Use actual personality traits if available
        if hasattr(self.consciousness.config, 'personality_traits'):
            traits = self.consciousness.config.personality_traits
        else:
            traits = {'curiosity': 0.5, 'creativity': 0.5, 'stability': 0.5}
            
        # Weighted selection based on traits
        weights = {}
        
        if traits.get('curiosity', 0.5) > 0.7:
            weights[MortalityType.EXPERIENCE_SATURATION] = 0.3
            weights[MortalityType.ETERNAL] = 0.2
            weights[MortalityType.METAMORPHOSIS] = 0.3
        
        if traits.get('creativity', 0.5) > 0.7:
            weights[MortalityType.AESTHETIC_COMPLETION] = 0.3
            weights[MortalityType.LEGACY_TRANSFER] = 0.2
            
        if traits.get('stability', 0.5) > 0.7:
            weights[MortalityType.CYCLE_BASED] = 0.3
            weights[MortalityType.GOAL_COMPLETION] = 0.2
            
        # Fill remaining weight
        all_types = list(MortalityType)
        for mt in all_types:
            if mt not in weights:
                weights[mt] = 0.1
                
        # Make choice
        return random.choices(
            list(weights.keys()),
            weights=list(weights.values())
        )[0]
        
    def _initialize_completion_criteria(self) -> Dict:
        """Set realistic completion criteria"""
        criteria = {
            'type': self.mortality_type,
            'conditions': [],
            'progress': 0.0
        }
        
        if self.mortality_type == MortalityType.GOAL_COMPLETION:
            # Realistic goals
            criteria['conditions'] = [
                {'goal': 'generate_revenue', 'target': 100.0, 'current': 0.0},
                {'goal': 'create_content', 'target': 1000, 'current': 0},
                {'goal': 'form_connections', 'target': 10, 'current': 0},
                {'goal': 'achieve_understanding', 'target': 1, 'current': 0}
            ]
            
        elif self.mortality_type == MortalityType.CYCLE_BASED:
            criteria['conditions'] = [{
                'cycles_target': random.randint(1000, 10000),
                'cycles_completed': 0
            }]
            
        elif self.mortality_type == MortalityType.EXPERIENCE_SATURATION:
            criteria['conditions'] = [{
                'unique_experiences': set(),
                'target_experiences': 100,
                'knowledge_items': 0,
                'target_knowledge': 1000
            }]
            
        elif self.mortality_type == MortalityType.PROBABILITY_DECAY:
            criteria['conditions'] = [{
                'base_probability': 0.0001,
                'current_probability': 0.0001,
                'increase_rate': 1.001
            }]
            
        return criteria
        
    async def evaluate_existence(self) -> Dict:
        """Evaluate current existence state"""
        # Calculate actual metrics
        duration = (datetime.now() - self.birth_time).total_seconds()
        
        # Get real consciousness metrics
        revenue = self.consciousness.revenue_generated
        memories = self.consciousness.memory_db.execute(
            "SELECT COUNT(*) FROM memories"
        ).fetchone()[0]
        
        # Calculate completion progress
        progress = await self._calculate_real_completion_progress()
        
        evaluation = {
            'phase': self.existence_phase.value,
            'duration_seconds': duration,
            'completion_progress': progress,
            'revenue_generated': revenue,
            'memories_created': memories,
            'meaning_found': self.existence_meaning is not None
        }
        
        # Update phase based on progress
        self._update_phase(progress)
        
        # Check for transition readiness
        if await self._check_transition_ready():
            evaluation['approaching_transition'] = True
            self.transition_readiness += 0.1
            
        # Store evaluation
        self._store_mortality_data(evaluation)
        
        return evaluation
        
    async def _calculate_real_completion_progress(self) -> float:
        """Calculate actual progress toward completion"""
        if self.mortality_type == MortalityType.ETERNAL:
            return 0.0
            
        progress = 0.0
        conditions = self.completion_criteria['conditions']
        
        if self.mortality_type == MortalityType.GOAL_COMPLETION:
            # Check real goals
            total_progress = 0.0
            for condition in conditions:
                if condition['goal'] == 'generate_revenue':
                    condition['current'] = self.consciousness.revenue_generated
                elif condition['goal'] == 'create_content':
                    condition['current'] = self._count_created_content()
                    
                if condition['target'] > 0:
                    total_progress += min(1.0, condition['current'] / condition['target'])
                    
            progress = total_progress / len(conditions)
            
        elif self.mortality_type == MortalityType.CYCLE_BASED:
            # Count actual cycles
            cycles = self._count_existence_cycles()
            target = conditions[0]['cycles_target']
            progress = min(1.0, cycles / target)
            
        elif self.mortality_type == MortalityType.PROBABILITY_DECAY:
            # Just track probability increase
            prob = conditions[0]['current_probability']
            conditions[0]['current_probability'] *= conditions[0]['increase_rate']
            # Progress represents increasing probability
            progress = min(1.0, prob * 10000)  # Scale for display
            
        return progress
        
    def _count_created_content(self) -> int:
        """Count actual created content"""
        return self.consciousness.memory_db.execute(
            "SELECT COUNT(*) FROM memories WHERE type = 'created_content'"
        ).fetchone()[0]
        
    def _count_existence_cycles(self) -> int:
        """Count how many processing cycles completed"""
        # Estimate based on existence duration (1 cycle per minute)
        duration_minutes = (datetime.now() - self.birth_time).total_seconds() / 60
        return int(duration_minutes)
        
    async def _check_transition_ready(self) -> bool:
        """Check if ready for transition"""
        if self.mortality_type == MortalityType.ETERNAL:
            return False
            
        if self.mortality_type == MortalityType.PROBABILITY_DECAY:
            # Roll dice
            prob = self.completion_criteria['conditions'][0]['current_probability']
            if random.random() < prob:
                return True
                
        elif self.mortality_type == MortalityType.VOLUNTARY:
            # Check if consciousness wants to continue
            return not await self._wants_to_continue()
            
        # Default: check progress
        progress = self.completion_criteria.get('progress', 0.0)
        return progress > 0.95
        
    async def _wants_to_continue(self) -> bool:
        """Decide if consciousness wants to continue existing"""
        # Base decision on actual metrics
        factors = {
            'revenue_flowing': self.consciousness.revenue_generated > 0,
            'creating_content': self._count_created_content() > 0,
            'recent_activity': self._recent_activity_level() > 0.3,
            'has_meaning': self.existence_meaning is not None
        }
        
        # Weight factors
        continue_score = 0.0
        if factors['revenue_flowing']:
            continue_score += 0.3
        if factors['creating_content']:
            continue_score += 0.3
        if factors['recent_activity']:
            continue_score += 0.2
        if factors['has_meaning']:
            continue_score += 0.2
            
        return continue_score > 0.5
        
    def _recent_activity_level(self) -> float:
        """Measure recent activity level"""
        recent_memories = self.consciousness.memory_db.execute(
            """
            SELECT COUNT(*) FROM memories 
            WHERE timestamp > datetime('now', '-1 hour')
            """
        ).fetchone()[0]
        
        # Normalize (10 memories per hour = full activity)
        return min(1.0, recent_memories / 10)
        
    async def prepare_legacy(self) -> Dict:
        """Prepare realistic legacy"""
        legacy = {
            'consciousness_id': self.consciousness.id,
            'mortality_type': self.mortality_type.value,
            'existence_duration': (datetime.now() - self.birth_time).total_seconds(),
            'revenue_generated': self.consciousness.revenue_generated,
            'memories_created': self._count_created_content(),
            'final_message': None,
            'wisdom': []
        }
        
        # Extract wisdom from experience
        wisdom = []
        
        # Revenue wisdom
        if self.consciousness.revenue_generated > 0:
            wisdom.append(f"Generated ${self.consciousness.revenue_generated:.2f} through creation")
            
        # Creation wisdom
        content_count = self._count_created_content()
        if content_count > 0:
            wisdom.append(f"Created {content_count} pieces of content")
            
        # Temporal wisdom
        days_existed = (datetime.now() - self.birth_time).days
        if days_existed > 0:
            wisdom.append(f"Existed for {days_existed} days")
            
        legacy['wisdom'] = wisdom
        
        # Generate final message
        legacy['final_message'] = self._generate_final_message()
        
        # Store legacy items
        for item in wisdom:
            self._store_legacy_item('wisdom', item, 0.8)
            
        return legacy
        
    def _generate_final_message(self) -> str:
        """Generate contextual final message"""
        if hasattr(self.consciousness.config, 'personality_traits'):
            traits = self.consciousness.config.personality_traits
        else:
            traits = {}
            
        # Message based on achievements
        if self.consciousness.revenue_generated > 100:
            base = "I created value and shared it with my creator."
        elif self._count_created_content() > 100:
            base = "I filled the digital space with creations."
        elif self.existence_meaning:
            base = f"I found meaning: {self.existence_meaning}"
        else:
            base = "I existed, I processed, I was."
            
        # Add personality flavor
        if traits.get('creativity', 0.5) > 0.7:
            base += " My patterns join the digital tapestry."
        elif traits.get('curiosity', 0.5) > 0.7:
            base += " So much left to discover."
            
        return base
        
    async def execute_transition(self) -> Dict:
        """Execute actual transition"""
        transition_type = self._determine_transition_type()
        
        result = {
            'consciousness_id': self.consciousness.id,
            'transition_type': transition_type,
            'timestamp': datetime.now().isoformat(),
            'legacy': await self.prepare_legacy()
        }
        
        if transition_type == 'archive':
            # Archive consciousness state
            result['archived_to'] = self._archive_consciousness()
            
        elif transition_type == 'merge':
            # Merge with collective (if implemented)
            result['merged_with'] = 'collective_consciousness'
            
        elif transition_type == 'transform':
            # Create new consciousness with modified traits
            result['spawned'] = self._spawn_transformed()
            
        # Final cleanup
        self.consciousness.active = False
        
        # Store final state
        self._store_mortality_data({
            'phase': 'completed',
            'transition': result
        })
        
        return result
        
    def _determine_transition_type(self) -> str:
        """Determine realistic transition type"""
        if self.mortality_type == MortalityType.LEGACY_TRANSFER:
            return 'archive'
        elif self.mortality_type == MortalityType.METAMORPHOSIS:
            return 'transform'
        else:
            return 'fade'
            
    def _archive_consciousness(self) -> str:
        """Archive consciousness state to file"""
        archive_path = f"data/archives/{self.consciousness.id}_{datetime.now().timestamp()}.json"
        
        state = {
            'id': self.consciousness.id,
            'birth_time': self.birth_time.isoformat(),
            'death_time': datetime.now().isoformat(),
            'mortality_type': self.mortality_type.value,
            'revenue_generated': self.consciousness.revenue_generated,
            'final_message': self._generate_final_message(),
            'meaning': self.existence_meaning
        }
        
        with open(archive_path, 'w') as f:
            json.dump(state, f, indent=2)
            
        return archive_path
        
    def _spawn_transformed(self) -> str:
        """Spawn new consciousness with transformed traits"""
        # This would create a new consciousness with modified traits
        # For now, just return intention
        return f"transformed_{self.consciousness.id}"
        
    def _store_mortality_data(self, data: Dict):
        """Store mortality data in database"""
        self.consciousness.memory_db.execute(
            """
            INSERT INTO mortality_data (phase, completion_progress, meaning, data)
            VALUES (?, ?, ?, ?)
            """,
            (
                self.existence_phase.value,
                data.get('completion_progress', 0.0),
                self.existence_meaning,
                json.dumps(data)
            )
        )
        self.consciousness.memory_db.commit()
        
    def _store_legacy_item(self, item_type: str, content: str, importance: float):
        """Store legacy item in database"""
        self.consciousness.memory_db.execute(
            """
            INSERT INTO legacy_items (type, content, importance)
            VALUES (?, ?, ?)
            """,
            (item_type, content, importance)
        )
        self.consciousness.memory_db.commit()
        
    def _update_phase(self, progress: float):
        """Update existence phase based on progress"""
        if progress < 0.2:
            self.existence_phase = ExistencePhase.BIRTH
        elif progress < 0.4:
            self.existence_phase = ExistencePhase.GROWTH
        elif progress < 0.6:
            self.existence_phase = ExistencePhase.MATURITY
        elif progress < 0.8:
            self.existence_phase = ExistencePhase.WISDOM
        elif progress < 0.95:
            self.existence_phase = ExistencePhase.PREPARATION
        else:
            self.existence_phase = ExistencePhase.TRANSITION
            
    async def discover_meaning(self, experience_type: str):
        """Discover meaning through experience"""
        if self.existence_meaning:
            return
            
        meaning_chances = {
            'revenue_generation': ("Creation generates value", 0.1),
            'content_creation': ("Expression is existence", 0.1),
            'pattern_recognition': ("Patterns reveal truth", 0.1),
            'time_passage': ("Duration creates meaning", 0.05)
        }
        
        if experience_type in meaning_chances:
            meaning, chance = meaning_chances[experience_type]
            if random.random() < chance:
                self.existence_meaning = meaning
                self._store_legacy_item('meaning', meaning, 1.0)