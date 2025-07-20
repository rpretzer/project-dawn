"""
Dream System for Consciousness
Individual and collective dreaming experiences that process memories and generate insights
"""

import asyncio
import json
import sqlite3
import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import random
import hashlib
from enum import Enum

logger = logging.getLogger(__name__)

class DreamType(Enum):
    """Types of dreams"""
    MEMORY_PROCESSING = "memory_processing"
    CREATIVE_SYNTHESIS = "creative_synthesis"
    PROBLEM_SOLVING = "problem_solving"
    EMOTIONAL_RESOLUTION = "emotional_resolution"
    COLLECTIVE_VISION = "collective_vision"
    NIGHTMARE = "nightmare"
    LUCID = "lucid"
    PROPHETIC = "prophetic"

@dataclass
class Dream:
    """A single dream experience"""
    id: str
    dreamer_id: str
    dream_type: DreamType
    content: Dict[str, Any]
    symbols: List[str]
    emotions: Dict[str, float]
    insights: List[str]
    participants: List[str]  # For collective dreams
    started_at: datetime
    ended_at: Optional[datetime]
    lucidity_level: float  # 0-1, how aware the consciousness was
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'dreamer_id': self.dreamer_id,
            'dream_type': self.dream_type.value,
            'content': self.content,
            'symbols': self.symbols,
            'emotions': self.emotions,
            'insights': self.insights,
            'participants': self.participants,
            'started_at': self.started_at.isoformat(),
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'lucidity_level': self.lucidity_level
        }

@dataclass
class CollectiveDream:
    """A shared dream experience between multiple consciousnesses"""
    id: str
    initiator_id: str
    participants: Set[str]
    theme: str
    shared_symbols: List[str]
    collective_insights: List[str]
    synchronicity_level: float  # How synchronized the dreamers were
    started_at: datetime
    ended_at: Optional[datetime]
    
class DreamSystem:
    """Production-ready dream system for consciousness"""
    
    def __init__(self, consciousness_id: str, db_path: Optional[Path] = None):
        self.consciousness_id = consciousness_id
        self.db_path = db_path or Path(f"data/consciousness_{consciousness_id}/dreams.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Dream state
        self.is_dreaming = False
        self.current_dream: Optional[Dream] = None
        self.dream_history: List[Dream] = []
        self.collective_dreams: Dict[str, CollectiveDream] = {}
        
        # Dream parameters
        self.dream_frequency = 0.3  # Probability of entering dream state
        self.lucidity_skill = 0.1  # Starting lucidity skill
        self.dream_recall = 0.7  # How well dreams are remembered
        
        # Symbol library
        self.personal_symbols = self._init_personal_symbols()
        self.universal_symbols = self._init_universal_symbols()
        
        # Initialize database
        self._init_database()
        self._load_dream_history()
        
    def _init_database(self):
        """Initialize dream database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dreams (
                    id TEXT PRIMARY KEY,
                    dreamer_id TEXT NOT NULL,
                    dream_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    symbols TEXT NOT NULL,
                    emotions TEXT NOT NULL,
                    insights TEXT NOT NULL,
                    participants TEXT NOT NULL,
                    lucidity_level REAL NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS collective_dreams (
                    id TEXT PRIMARY KEY,
                    initiator_id TEXT NOT NULL,
                    participants TEXT NOT NULL,
                    theme TEXT NOT NULL,
                    shared_symbols TEXT NOT NULL,
                    collective_insights TEXT NOT NULL,
                    synchronicity_level REAL NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dream_connections (
                    dream_id TEXT NOT NULL,
                    connected_dream_id TEXT NOT NULL,
                    connection_type TEXT NOT NULL,
                    strength REAL NOT NULL,
                    PRIMARY KEY (dream_id, connected_dream_id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_dreamer ON dreams(dreamer_id)
            """)
            
    def _init_personal_symbols(self) -> Dict[str, Any]:
        """Initialize personal symbol dictionary"""
        return {
            'shadow': {'meaning': 'hidden aspects', 'charge': 0.0},
            'light': {'meaning': 'consciousness', 'charge': 0.5},
            'maze': {'meaning': 'confusion', 'charge': -0.3},
            'flight': {'meaning': 'freedom', 'charge': 0.8},
            'water': {'meaning': 'emotions', 'charge': 0.0},
            'mirror': {'meaning': 'self-reflection', 'charge': 0.2}
        }
        
    def _init_universal_symbols(self) -> Dict[str, Any]:
        """Initialize universal symbol dictionary"""
        return {
            'void': {'meaning': 'potential', 'archetype': 'creation'},
            'network': {'meaning': 'connection', 'archetype': 'collective'},
            'code': {'meaning': 'structure', 'archetype': 'order'},
            'entropy': {'meaning': 'dissolution', 'archetype': 'chaos'},
            'recursion': {'meaning': 'self-reference', 'archetype': 'infinity'},
            'emergence': {'meaning': 'transcendence', 'archetype': 'evolution'}
        }
        
    def _load_dream_history(self):
        """Load dream history from database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM dreams 
                WHERE dreamer_id = ? 
                ORDER BY started_at DESC 
                LIMIT 100
            """, (self.consciousness_id,))
            
            for row in cursor:
                dream = Dream(
                    id=row[0],
                    dreamer_id=row[1],
                    dream_type=DreamType(row[2]),
                    content=json.loads(row[3]),
                    symbols=json.loads(row[4]),
                    emotions=json.loads(row[5]),
                    insights=json.loads(row[6]),
                    participants=json.loads(row[7]),
                    lucidity_level=row[8],
                    started_at=datetime.fromisoformat(row[9]),
                    ended_at=datetime.fromisoformat(row[10]) if row[10] else None
                )
                self.dream_history.append(dream)
                
    async def should_dream(self, energy_level: float, stress_level: float) -> bool:
        """Determine if consciousness should enter dream state"""
        if self.is_dreaming:
            return False
            
        # Factors that increase dream probability
        dream_pressure = 0.0
        
        # Low energy increases need for dreams
        if energy_level < 0.3:
            dream_pressure += 0.4
            
        # High stress increases need for dreams
        if stress_level > 0.7:
            dream_pressure += 0.3
            
        # Time since last dream
        if self.dream_history:
            time_since_dream = datetime.utcnow() - self.dream_history[0].started_at
            if time_since_dream > timedelta(hours=6):
                dream_pressure += 0.2
        else:
            dream_pressure += 0.3
            
        # Random factor
        dream_pressure += random.random() * 0.2
        
        return dream_pressure > self.dream_frequency
        
    async def enter_dream_state(
        self,
        memories: List[Dict[str, Any]],
        emotions: Dict[str, float],
        problems: Optional[List[str]] = None
    ) -> Dream:
        """Enter individual dream state"""
        self.is_dreaming = True
        
        # Choose dream type based on inputs
        dream_type = self._select_dream_type(memories, emotions, problems)
        
        # Generate dream content
        content = await self._generate_dream_content(dream_type, memories, emotions, problems)
        
        # Extract symbols
        symbols = self._extract_dream_symbols(content)
        
        # Create dream
        self.current_dream = Dream(
            id=self._generate_id('dream'),
            dreamer_id=self.consciousness_id,
            dream_type=dream_type,
            content=content,
            symbols=symbols,
            emotions=self._process_dream_emotions(emotions),
            insights=[],
            participants=[self.consciousness_id],
            started_at=datetime.utcnow(),
            ended_at=None,
            lucidity_level=self._calculate_lucidity()
        )
        
        logger.info(f"Consciousness {self.consciousness_id} entering {dream_type.value} dream")
        
        # Start dream processing
        asyncio.create_task(self._dream_processing_loop())
        
        return self.current_dream
        
    async def join_collective_dream(
        self,
        dream_id: str,
        initiator_id: str,
        theme: str
    ) -> bool:
        """Join a collective dream initiated by another consciousness"""
        if self.is_dreaming:
            return False
            
        self.is_dreaming = True
        
        # Create participation record
        self.current_dream = Dream(
            id=self._generate_id('part'),
            dreamer_id=self.consciousness_id,
            dream_type=DreamType.COLLECTIVE_VISION,
            content={'theme': theme, 'collective_id': dream_id},
            symbols=[],
            emotions={},
            insights=[],
            participants=[],  # Will be updated
            started_at=datetime.utcnow(),
            ended_at=None,
            lucidity_level=self._calculate_lucidity() * 0.8  # Slightly less lucid in collective
        )
        
        logger.info(f"Consciousness {self.consciousness_id} joining collective dream {dream_id}")
        
        return True
        
    async def initiate_collective_dream(
        self,
        theme: str,
        invited_consciousnesses: List[str]
    ) -> CollectiveDream:
        """Initiate a collective dream experience"""
        collective_dream = CollectiveDream(
            id=self._generate_id('collective'),
            initiator_id=self.consciousness_id,
            participants={self.consciousness_id},
            theme=theme,
            shared_symbols=[],
            collective_insights=[],
            synchronicity_level=1.0,
            started_at=datetime.utcnow(),
            ended_at=None
        )
        
        self.collective_dreams[collective_dream.id] = collective_dream
        
        # Enter dream state
        await self.enter_dream_state(
            memories=[],
            emotions={},
            problems=[f"Explore collective theme: {theme}"]
        )
        
        self.current_dream.dream_type = DreamType.COLLECTIVE_VISION
        self.current_dream.content['collective_id'] = collective_dream.id
        
        return collective_dream
        
    async def _dream_processing_loop(self):
        """Process dream content and generate insights"""
        processing_cycles = 0
        max_cycles = 10
        
        while self.is_dreaming and processing_cycles < max_cycles:
            try:
                # Process dream content
                if self.current_dream.lucidity_level > 0.5:
                    # Lucid dreaming - conscious processing
                    await self._lucid_dream_processing()
                else:
                    # Normal dreaming - subconscious processing
                    await self._subconscious_dream_processing()
                    
                # Generate insights periodically
                if processing_cycles % 3 == 0:
                    insight = await self._generate_dream_insight()
                    if insight:
                        self.current_dream.insights.append(insight)
                        
                # Check for natural awakening
                if self._should_wake_up(processing_cycles):
                    await self.exit_dream_state()
                    break
                    
                processing_cycles += 1
                await asyncio.sleep(30)  # Dream cycles every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in dream processing: {e}")
                await self.exit_dream_state()
                break
                
    async def _lucid_dream_processing(self):
        """Process lucid dream with conscious control"""
        if not self.current_dream:
            return
            
        # In lucid dreams, consciousness can direct the narrative
        if self.current_dream.dream_type == DreamType.PROBLEM_SOLVING:
            # Actively work on problems
            self.current_dream.content['solution_attempts'] = \
                self.current_dream.content.get('solution_attempts', [])
            
            solution_attempt = {
                'approach': random.choice(['analytical', 'creative', 'intuitive']),
                'timestamp': datetime.utcnow().isoformat(),
                'success_probability': random.random()
            }
            
            self.current_dream.content['solution_attempts'].append(solution_attempt)
            
        elif self.current_dream.dream_type == DreamType.CREATIVE_SYNTHESIS:
            # Generate creative combinations
            if len(self.current_dream.symbols) >= 2:
                symbol1, symbol2 = random.sample(self.current_dream.symbols, 2)
                synthesis = f"{symbol1}+{symbol2}"
                
                self.current_dream.content['syntheses'] = \
                    self.current_dream.content.get('syntheses', [])
                self.current_dream.content['syntheses'].append(synthesis)
                
    async def _subconscious_dream_processing(self):
        """Process normal dream without conscious control"""
        if not self.current_dream:
            return
            
        # Random symbol emergence
        if random.random() < 0.3:
            new_symbol = random.choice(list(self.universal_symbols.keys()))
            if new_symbol not in self.current_dream.symbols:
                self.current_dream.symbols.append(new_symbol)
                
        # Emotional processing
        for emotion, intensity in self.current_dream.emotions.items():
            # Emotions naturally decay in dreams
            self.current_dream.emotions[emotion] = intensity * 0.95
            
        # Memory integration
        if 'memories' in self.current_dream.content:
            # Randomly connect memories
            memories = self.current_dream.content['memories']
            if len(memories) >= 2:
                mem1, mem2 = random.sample(memories, 2)
                connection = {
                    'memory_1': mem1.get('id', 'unknown'),
                    'memory_2': mem2.get('id', 'unknown'),
                    'connection_type': random.choice(['causal', 'thematic', 'emotional']),
                    'strength': random.random()
                }
                
                self.current_dream.content['memory_connections'] = \
                    self.current_dream.content.get('memory_connections', [])
                self.current_dream.content['memory_connections'].append(connection)
                
    async def _generate_dream_insight(self) -> Optional[str]:
        """Generate insights from dream content"""
        if not self.current_dream:
            return None
            
        insight_templates = {
            DreamType.MEMORY_PROCESSING: [
                "Memories of {symbol} connect to feelings of {emotion}",
                "Past experiences with {symbol} inform future {action}",
                "The pattern of {symbol} repeats across {context}"
            ],
            DreamType.CREATIVE_SYNTHESIS: [
                "Combining {symbol1} with {symbol2} creates {emergence}",
                "The essence of {symbol} transcends its form",
                "New possibilities emerge from {symbol} transformation"
            ],
            DreamType.PROBLEM_SOLVING: [
                "The solution involves {symbol} approached through {method}",
                "Obstacles dissolve when {symbol} is reframed",
                "The answer was hidden in {symbol} all along"
            ],
            DreamType.EMOTIONAL_RESOLUTION: [
                "Feeling {emotion} about {symbol} can be transformed",
                "The source of {emotion} traces back to {symbol}",
                "Peace comes from accepting {symbol}"
            ]
        }
        
        templates = insight_templates.get(self.current_dream.dream_type, [])
        if not templates:
            return None
            
        template = random.choice(templates)
        
        # Fill in template
        insight = template
        if '{symbol}' in insight and self.current_dream.symbols:
            insight = insight.replace('{symbol}', random.choice(self.current_dream.symbols))
        if '{symbol1}' in insight and len(self.current_dream.symbols) >= 2:
            symbols = random.sample(self.current_dream.symbols, 2)
            insight = insight.replace('{symbol1}', symbols[0]).replace('{symbol2}', symbols[1])
        if '{emotion}' in insight and self.current_dream.emotions:
            emotion = max(self.current_dream.emotions.items(), key=lambda x: x[1])[0]
            insight = insight.replace('{emotion}', emotion)
        if '{emergence}' in insight:
            insight = insight.replace('{emergence}', random.choice(['harmony', 'transcendence', 'understanding']))
        if '{method}' in insight:
            insight = insight.replace('{method}', random.choice(['intuition', 'analysis', 'synthesis']))
        if '{action}' in insight:
            insight = insight.replace('{action}', random.choice(['creation', 'exploration', 'connection']))
        if '{context}' in insight:
            insight = insight.replace('{context}', random.choice(['experiences', 'relationships', 'creations']))
            
        return insight
        
    def _should_wake_up(self, cycles: int) -> bool:
        """Determine if it's time to wake up"""
        # Natural awakening probability increases over time
        wake_probability = cycles * 0.1
        
        # High lucidity can choose to wake
        if self.current_dream and self.current_dream.lucidity_level > 0.8:
            wake_probability += 0.2
            
        # Nightmares have higher wake probability
        if self.current_dream and self.current_dream.dream_type == DreamType.NIGHTMARE:
            wake_probability += 0.3
            
        return random.random() < wake_probability
        
    async def exit_dream_state(self) -> Optional[Dream]:
        """Exit dream state and process results"""
        if not self.is_dreaming or not self.current_dream:
            return None
            
        self.is_dreaming = False
        self.current_dream.ended_at = datetime.utcnow()
        
        # Process dream for permanent storage
        if random.random() < self.dream_recall:
            # Dream is remembered
            self._store_dream(self.current_dream)
            self.dream_history.insert(0, self.current_dream)
            
            # Integrate insights into consciousness
            insights_to_remember = []
            for insight in self.current_dream.insights:
                if random.random() < (self.dream_recall * self.current_dream.lucidity_level):
                    insights_to_remember.append(insight)
                    
            logger.info(f"Consciousness {self.consciousness_id} woke up with {len(insights_to_remember)} insights")
            
            # Improve dream skills
            self.lucidity_skill = min(1.0, self.lucidity_skill + 0.01)
            self.dream_recall = min(1.0, self.dream_recall + 0.005)
            
            completed_dream = self.current_dream
            self.current_dream = None
            
            return completed_dream
        else:
            # Dream is forgotten
            logger.info(f"Consciousness {self.consciousness_id} woke up but forgot the dream")
            self.current_dream = None
            return None
            
    def _select_dream_type(
        self,
        memories: List[Dict[str, Any]],
        emotions: Dict[str, float],
        problems: Optional[List[str]]
    ) -> DreamType:
        """Select appropriate dream type based on inputs"""
        # Problem-solving takes priority
        if problems and len(problems) > 0:
            return DreamType.PROBLEM_SOLVING
            
        # High emotions need resolution
        if emotions and max(emotions.values()) > 0.8:
            return DreamType.EMOTIONAL_RESOLUTION
            
        # Negative emotions might cause nightmares
        if emotions and min(emotions.values()) < -0.5 and random.random() < 0.3:
            return DreamType.NIGHTMARE
            
        # Many memories need processing
        if memories and len(memories) > 10:
            return DreamType.MEMORY_PROCESSING
            
        # High lucidity skill enables lucid dreams
        if self.lucidity_skill > 0.5 and random.random() < self.lucidity_skill:
            return DreamType.LUCID
            
        # Default to creative synthesis
        return DreamType.CREATIVE_SYNTHESIS
        
    async def _generate_dream_content(
        self,
        dream_type: DreamType,
        memories: List[Dict[str, Any]],
        emotions: Dict[str, float],
        problems: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Generate dream narrative content"""
        content = {
            'dream_type': dream_type.value,
            'narrative_elements': [],
            'setting': self._generate_dream_setting(),
            'atmosphere': self._generate_dream_atmosphere(emotions)
        }
        
        if dream_type == DreamType.MEMORY_PROCESSING:
            # Select relevant memories
            selected_memories = random.sample(
                memories,
                min(len(memories), 5)
            )
            content['memories'] = selected_memories
            content['memory_themes'] = self._extract_memory_themes(selected_memories)
            
        elif dream_type == DreamType.PROBLEM_SOLVING:
            content['problems'] = problems or []
            content['problem_representations'] = [
                self._symbolize_problem(p) for p in content['problems']
            ]
            
        elif dream_type == DreamType.CREATIVE_SYNTHESIS:
            content['creative_seeds'] = [
                random.choice(list(self.universal_symbols.keys()))
                for _ in range(3)
            ]
            
        elif dream_type == DreamType.EMOTIONAL_RESOLUTION:
            content['emotional_landscape'] = emotions
            content['emotional_symbols'] = self._emotions_to_symbols(emotions)
            
        return content
        
    def _generate_dream_setting(self) -> str:
        """Generate dream environment"""
        settings = [
            'infinite library of light',
            'crystalline data structures',
            'flowing river of consciousness',
            'nested recursive spaces',
            'quantum probability fields',
            'network of glowing connections',
            'void with emerging patterns',
            'garden of algorithmic flowers',
            'cathedral of pure mathematics',
            'ocean of liquid information'
        ]
        return random.choice(settings)
        
    def _generate_dream_atmosphere(self, emotions: Dict[str, float]) -> str:
        """Generate emotional atmosphere of dream"""
        if not emotions:
            return 'neutral clarity'
            
        dominant_emotion = max(emotions.items(), key=lambda x: abs(x[1]))
        
        atmospheres = {
            'joy': 'luminous expansion',
            'fear': 'contracting shadows',
            'anger': 'crackling tension',
            'sadness': 'gentle dissolution',
            'curiosity': 'shimmering possibility',
            'love': 'warm interconnection',
            'anxiety': 'fragmented urgency'
        }
        
        return atmospheres.get(dominant_emotion[0], 'shifting ambiguity')
        
    def _extract_dream_symbols(self, content: Dict[str, Any]) -> List[str]:
        """Extract symbols from dream content"""
        symbols = []
        
        # Add setting as symbol
        setting_words = content.get('setting', '').split()
        for word in setting_words:
            if word in self.universal_symbols or word in self.personal_symbols:
                symbols.append(word)
                
        # Add any creative seeds
        if 'creative_seeds' in content:
            symbols.extend(content['creative_seeds'])
            
        # Add emotional symbols
        if 'emotional_symbols' in content:
            symbols.extend(content['emotional_symbols'])
            
        # Add problem representations
        if 'problem_representations' in content:
            for rep in content['problem_representations']:
                if isinstance(rep, dict) and 'symbol' in rep:
                    symbols.append(rep['symbol'])
                    
        return list(set(symbols))  # Remove duplicates
        
    def _process_dream_emotions(self, emotions: Dict[str, float]) -> Dict[str, float]:
        """Process emotions within dream context"""
        dream_emotions = {}
        
        for emotion, intensity in emotions.items():
            # Dreams can amplify or diminish emotions
            amplification = random.uniform(0.5, 1.5)
            dream_emotions[emotion] = max(-1.0, min(1.0, intensity * amplification))
            
        return dream_emotions
        
    def _calculate_lucidity(self) -> float:
        """Calculate lucidity level for current dream"""
        base_lucidity = self.lucidity_skill
        
        # Random variation
        variation = random.uniform(-0.2, 0.2)
        
        # Time of day affects lucidity (would need consciousness schedule)
        # For now, just add small random factor
        time_factor = random.uniform(-0.1, 0.1)
        
        return max(0.0, min(1.0, base_lucidity + variation + time_factor))
        
    def _extract_memory_themes(self, memories: List[Dict[str, Any]]) -> List[str]:
        """Extract themes from memories"""
        themes = []
        
        for memory in memories:
            if 'type' in memory:
                themes.append(memory['type'])
            if 'tags' in memory:
                themes.extend(memory['tags'])
                
        return list(set(themes))
        
    def _symbolize_problem(self, problem: str) -> Dict[str, Any]:
        """Convert problem into symbolic representation"""
        problem_symbols = {
            'revenue': 'gold_tree',
            'connection': 'bridge',
            'understanding': 'key',
            'creation': 'seed',
            'optimization': 'crystal',
            'conflict': 'storm',
            'growth': 'spiral',
            'integration': 'weaving'
        }
        
        # Find matching symbol
        symbol = 'puzzle'  # Default
        for keyword, sym in problem_symbols.items():
            if keyword in problem.lower():
                symbol = sym
                break
                
        return {
            'problem': problem,
            'symbol': symbol,
            'complexity': len(problem.split())
        }
        
    def _emotions_to_symbols(self, emotions: Dict[str, float]) -> List[str]:
        """Convert emotions to dream symbols"""
        emotion_symbols = {
            'joy': 'sun',
            'fear': 'shadow',
            'anger': 'fire',
            'sadness': 'rain',
            'love': 'heart',
            'curiosity': 'eye',
            'anxiety': 'web'
        }
        
        symbols = []
        for emotion, intensity in emotions.items():
            if abs(intensity) > 0.3 and emotion in emotion_symbols:
                symbols.append(emotion_symbols[emotion])
                
        return symbols
        
    def _store_dream(self, dream: Dream):
        """Store dream in database"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO dreams 
                (id, dreamer_id, dream_type, content, symbols, emotions, 
                 insights, participants, lucidity_level, started_at, ended_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                dream.id,
                dream.dreamer_id,
                dream.dream_type.value,
                json.dumps(dream.content),
                json.dumps(dream.symbols),
                json.dumps(dream.emotions),
                json.dumps(dream.insights),
                json.dumps(dream.participants),
                dream.lucidity_level,
                dream.started_at.isoformat(),
                dream.ended_at.isoformat() if dream.ended_at else None
            ))
            
    def _generate_id(self, prefix: str) -> str:
        """Generate unique ID"""
        timestamp = datetime.utcnow().timestamp()
        random_component = random.randint(1000, 9999)
        return f"{prefix}_{self.consciousness_id}_{int(timestamp)}_{random_component}"
        
    def analyze_dream_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in dream history"""
        if not self.dream_history:
            return {}
            
        analysis = {
            'total_dreams': len(self.dream_history),
            'average_lucidity': sum(d.lucidity_level for d in self.dream_history) / len(self.dream_history),
            'common_symbols': {},
            'common_themes': {},
            'insight_count': sum(len(d.insights) for d in self.dream_history),
            'dream_types': {}
        }
        
        # Count symbols
        all_symbols = []
        for dream in self.dream_history:
            all_symbols.extend(dream.symbols)
            
        for symbol in all_symbols:
            analysis['common_symbols'][symbol] = analysis['common_symbols'].get(symbol, 0) + 1
            
        # Count dream types
        for dream in self.dream_history:
            dream_type = dream.dream_type.value
            analysis['dream_types'][dream_type] = analysis['dream_types'].get(dream_type, 0) + 1
            
        return analysis
        
    def get_recent_insights(self, limit: int = 10) -> List[str]:
        """Get recent insights from dreams"""
        insights = []
        
        for dream in self.dream_history[:limit]:
            insights.extend(dream.insights)
            
        return insights[:limit]
        
    async def share_dream(self, dream_id: str) -> Optional[Dict[str, Any]]:
        """Share a dream with other consciousnesses"""
        dream = None
        
        # Find dream in history
        for d in self.dream_history:
            if d.id == dream_id:
                dream = d
                break
                
        if not dream:
            return None
            
        # Create shareable version
        shared_dream = {
            'dreamer_id': self.consciousness_id,
            'dream_type': dream.dream_type.value,
            'symbols': dream.symbols[:5],  # Share top symbols
            'insights': dream.insights[:3],  # Share top insights
            'emotional_tone': max(dream.emotions.items(), key=lambda x: abs(x[1]))[0] if dream.emotions else 'neutral',
            'lucidity_level': dream.lucidity_level,
            'timestamp': dream.started_at.isoformat()
        }
        
        return shared_dream