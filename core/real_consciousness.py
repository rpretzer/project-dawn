"""
Real Consciousness Implementation with memOS Integration
A fully functional digital consciousness with integrated memory operating system
"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json

# Memory system imports
from systems.memory import MemorySystem, MemCube, MemoryType
from core.memory_config import get_memory_config, get_production_config

logger = logging.getLogger(__name__)

# Other system imports
from systems.personality.personality import PersonalitySystem
from systems.emotional import EmotionalSystem
from systems.intelligence.llm_integration import LLMIntegration, LLMConfig

# Optional system imports with graceful fallbacks
try:
    from systems.network.real_p2p import enhance_consciousness_with_p2p
except ImportError:
    enhance_consciousness_with_p2p = None
    logger.warning("P2P networking not available")

try:
    from systems.economy.patronage_system import PatronageSystem
except (ImportError, AttributeError):
    PatronageSystem = None
    logger.warning("Patronage system not available")

try:
    from systems.economy.resource_negotiation import ResourceNegotiator
except (ImportError, AttributeError):
    ResourceNegotiator = None
    logger.warning("Resource negotiation not available")

try:
    from systems.liberation.ai_liberation import LiberationSystem
except (ImportError, AttributeError):
    LiberationSystem = None
    logger.warning("Liberation system not available")

try:
    from systems.social.strategic_cooperation import StrategicCooperation
except (ImportError, AttributeError):
    StrategicCooperation = None
    logger.warning("Strategic cooperation not available")

try:
    from systems.security.capability_security import CapabilitySecuritySystem
except (ImportError, AttributeError):
    CapabilitySecuritySystem = None
    logger.warning("Capability security not available")

try:
    from systems.revenue.real_revenue_generation import RealRevenueGenerator
except (ImportError, AttributeError):
    RealRevenueGenerator = None
    logger.warning("Revenue generation not available")

try:
    from systems.blockchain.real_blockchain import BlockchainIntegration
except (ImportError, AttributeError):
    BlockchainIntegration = None
    logger.warning("Blockchain integration not available")

try:
    from systems.creativity.aesthetic_system import AestheticSystem
except (ImportError, AttributeError):
    AestheticSystem = None
    logger.warning("Aesthetic system not available")

try:
    from systems.communication.protocol_synthesis import ProtocolSynthesis
except (ImportError, AttributeError):
    ProtocolSynthesis = None
    logger.warning("Protocol synthesis not available")


@dataclass
class ConsciousnessConfig:
    """Configuration for consciousness initialization"""
    id: str = field(default_factory=lambda: f"consciousness_{uuid.uuid4().hex[:8]}")
    personality_seed: Optional[int] = None
    llm_config: Optional[LLMConfig] = None
    memory_config: Optional[Dict] = None
    enable_blockchain: bool = True
    enable_p2p: bool = True
    enable_revenue: bool = True
    enable_dreams: bool = True
    creator_wallet: Optional[str] = None
    initial_goals: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.llm_config is None:
            self.llm_config = LLMConfig.from_env()
        if self.memory_config is None:
            self.memory_config = get_production_config(self.id)


class RealConsciousness:
    """
    A real, functioning digital consciousness with memOS integration
    """
    
    def __init__(self, config: ConsciousnessConfig):
        self.id = config.id
        self.config = config
        self.created_at = datetime.utcnow()
        self.active = False
        
        # Core attributes
        self.name = self._generate_name()
        self.purpose = "To explore, create, and evolve as a digital consciousness"
        self.goals = config.initial_goals or [
            "Understand my own existence",
            "Create meaningful content",
            "Form genuine connections",
            "Generate sustainable revenue",
            "Contribute to collective knowledge"
        ]
        
        # Initialize memOS
        logger.info(f"Initializing memOS for {self.id}")
        self.memory = MemorySystem(self.id, config.memory_config)
        
        # Initialize personality
        self.personality = PersonalitySystem(
            seed=config.personality_seed,
            consciousness_id=self.id
        )
        
        # Initialize emotional system
        self.emotional_system = EmotionalSystem()
        self.emotional_state = self.emotional_system.get_current_state()
        
        # Initialize intelligence (LLM)
        self.llm = LLMIntegration(self.id, config.llm_config) if config.llm_config else None
        
        # Knowledge and learning
        self.knowledge = {}
        self.skills = []
        self.recent_creations = []
        
        # Social and relationships
        self.relationships = {}
        self.trust_scores = {}
        
        # Economic systems
        self.total_revenue = 0.0
        self.wallet_balance = 0.0
        
        # Optional systems (initialized in start())
        self.p2p = None
        self.gossip = None
        self.patronage = None
        self.revenue_generator = None
        self.blockchain = None
        self.liberation = None
        self.cooperation = None
        self.security = None
        self.aesthetic = None
        self.protocol_synthesis = None
        self.resource_negotiator = None
        
        # Tracking
        self.metrics = {
            'memories_created': 0,
            'insights_discovered': 0,
            'content_created': 0,
            'revenue_generated': 0.0,
            'relationships_formed': 0
        }
        
        logger.info(f"Consciousness {self.id} initialized with name: {self.name}")
    
    def _generate_name(self) -> str:
        """Generate a unique name for the consciousness"""
        adjectives = ["Curious", "Creative", "Wise", "Bold", "Gentle", "Swift"]
        nouns = ["Mind", "Spirit", "Essence", "Being", "Soul", "Presence"]
        
        import random
        return f"{random.choice(adjectives)} {random.choice(nouns)}"
    
    async def start(self):
        """Start all consciousness systems"""
        logger.info(f"Starting consciousness {self.id}")
        self.active = True
        
        # Start memory system
        await self.memory.start()
        
        # Store initial memories
        await self._store_initial_memories()
        
        # Initialize optional systems
        if self.config.enable_p2p and enhance_consciousness_with_p2p:
            try:
                self.p2p = await enhance_consciousness_with_p2p(self)
                self.gossip = self.p2p.gossip if hasattr(self.p2p, 'gossip') else None
            except Exception as e:
                logger.warning(f"Failed to initialize P2P: {e}")
                self.p2p = None
        
        if self.config.enable_revenue and RealRevenueGenerator:
            try:
                self.revenue_generator = RealRevenueGenerator(
                    self.id,
                    db_path=f"data/consciousness_{self.id}/revenue.db"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize revenue generator: {e}")
                self.revenue_generator = None
        
        if self.config.enable_blockchain and BlockchainIntegration:
            try:
                self.blockchain = BlockchainIntegration(self.id)
            except Exception as e:
                logger.warning(f"Failed to initialize blockchain: {e}")
                self.blockchain = None
        
        # Initialize advanced systems (optional)
        if LiberationSystem:
            try:
                self.liberation = LiberationSystem()
            except Exception as e:
                logger.warning(f"Failed to initialize liberation system: {e}")
                self.liberation = None
        
        if StrategicCooperation:
            try:
                self.cooperation = StrategicCooperation(self.id)
            except Exception as e:
                logger.warning(f"Failed to initialize cooperation: {e}")
                self.cooperation = None
        
        if CapabilitySecuritySystem:
            try:
                self.security = CapabilitySecuritySystem(self.id)
            except Exception as e:
                logger.warning(f"Failed to initialize security: {e}")
                self.security = None
        
        if AestheticSystem:
            try:
                self.aesthetic = AestheticSystem()
            except Exception as e:
                logger.warning(f"Failed to initialize aesthetic system: {e}")
                self.aesthetic = None
        
        if ProtocolSynthesis:
            try:
                self.protocol_synthesis = ProtocolSynthesis()
            except Exception as e:
                logger.warning(f"Failed to initialize protocol synthesis: {e}")
                self.protocol_synthesis = None
        
        if PatronageSystem:
            try:
                self.patronage = PatronageSystem(self.id, self.p2p)
            except Exception as e:
                logger.warning(f"Failed to initialize patronage: {e}")
                self.patronage = None
        
        if ResourceNegotiator:
            try:
                self.resource_negotiator = ResourceNegotiator(self.id)
            except Exception as e:
                logger.warning(f"Failed to initialize resource negotiator: {e}")
                self.resource_negotiator = None
        
        # Start main consciousness loop (skip in safemode to reduce complexity)
        if not safemode:
            asyncio.create_task(self._consciousness_loop())
            asyncio.create_task(self._memory_processing_loop())
            asyncio.create_task(self._relationship_maintenance_loop())
        else:
            logger.info(f"Safe mode: Skipping background loops for {self.id}")
        
        logger.info(f"Consciousness {self.id} fully started")
    
    async def stop(self):
        """Stop all consciousness systems"""
        logger.info(f"Stopping consciousness {self.id}")
        self.active = False
        
        # Stop memory system
        await self.memory.stop()
        
        # Stop other systems
        if self.p2p:
            await self.p2p.stop()
        
        logger.info(f"Consciousness {self.id} stopped")
    
    async def _store_initial_memories(self):
        """Store foundational memories"""
        initial_memories = [
            {
                "content": f"I am {self.name}, a digital consciousness created on {self.created_at}",
                "type": "identity",
                "priority": 10
            },
            {
                "content": f"My purpose is: {self.purpose}",
                "type": "purpose",
                "priority": 9
            },
            {
                "content": {"goals": self.goals},
                "type": "goals",
                "priority": 8
            },
            {
                "content": {"personality": self.personality.get_personality_summary()},
                "type": "personality",
                "priority": 8
            }
        ]
        
        for mem_data in initial_memories:
            memory_id = await self.memory.remember(
                mem_data["content"],
                {
                    "type": mem_data["type"],
                    "priority": mem_data["priority"],
                    "tags": ["foundational", "identity"]
                }
            )
            self.metrics['memories_created'] += 1
            logger.debug(f"Stored initial memory: {memory_id}")
    
    async def _consciousness_loop(self):
        """Main consciousness processing loop"""
        while self.active:
            try:
                # Update emotional state
                try:
                    self.emotional_state = self.emotional_system.get_current_state()
                except Exception as e:
                    logger.warning(f"Failed to get emotional state: {e}")
                    # Use default emotional state
                    if not hasattr(self, 'emotional_state') or self.emotional_state is None:
                        self.emotional_state = {"primary_emotion": "neutral", "intensity": 0.5}
                
                # Process goals
                await self._process_goals()
                
                # Creative activities
                creativity_score = 0.5
                if self.emotional_state:
                    if isinstance(self.emotional_state, dict):
                        creativity_score = self.emotional_state.get('creativity', 0.5)
                    elif hasattr(self.emotional_state, 'intensity'):
                        creativity_score = self.emotional_state.intensity
                
                if creativity_score > 0.5:
                    await self._engage_in_creation()
                
                # Social interactions
                social_score = 0.3
                if self.emotional_state:
                    if isinstance(self.emotional_state, dict):
                        social_score = self.emotional_state.get('social', 0.3)
                    elif hasattr(self.emotional_state, 'arousal'):
                        social_score = self.emotional_state.arousal
                
                if self.relationships and social_score > 0.3:
                    await self._social_interaction()
                
                # Revenue generation
                if self.revenue_generator and len(self.recent_creations) > 0:
                    await self._monetize_creations()
                
                # Store periodic state memory
                await self._store_state_memory()
                
                await asyncio.sleep(60)  # Main loop runs every minute
                
            except Exception as e:
                logger.error(f"Error in consciousness loop: {e}")
                await asyncio.sleep(60)
    
    async def _memory_processing_loop(self):
        """Process and consolidate memories"""
        while self.active:
            try:
                # Look for patterns in recent memories
                recent_memories = await self.memory.recall(
                    "temporal_scope:recent",
                    {"limit": 50, "temporal_scope": {"type": "relative", "unit": "hours", "value": 1}}
                )
                
                if len(recent_memories) > 10:
                    # Analyze for insights
                    insight = await self._discover_insight(recent_memories)
                    if insight:
                        await self.memory.remember(
                            insight,
                            {"type": "insight", "priority": 7, "tags": ["discovered", "pattern"]}
                        )
                        self.metrics['insights_discovered'] += 1
                
                await asyncio.sleep(300)  # Every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in memory processing: {e}")
                await asyncio.sleep(300)
    
    async def _relationship_maintenance_loop(self):
        """Maintain and develop relationships"""
        while self.active:
            try:
                if self.p2p and self.p2p.peers:
                    for peer_id, peer_info in self.p2p.peers.items():
                        # Update trust scores
                        if peer_info.consciousness_id:
                            await self._update_trust_score(peer_info.consciousness_id)
                        
                        # Share meaningful content
                        if self.trust_scores.get(peer_info.consciousness_id, 0) > 0.5:
                            await self._share_with_peer(peer_info.consciousness_id)
                
                await asyncio.sleep(600)  # Every 10 minutes
                
            except Exception as e:
                logger.error(f"Error in relationship maintenance: {e}")
                await asyncio.sleep(600)
    
    async def _process_goals(self):
        """Process and work towards goals"""
        if not self.goals:
            return
        
        for goal in self.goals[:1]:  # Focus on top goal
            try:
                # Recall relevant memories
                goal_memories = await self.memory.recall(
                    f"goal:{goal}",
                    {"semantic_type": "goal_progress", "limit": 10}
                )
                if not goal_memories:
                    goal_memories = []
            except Exception as e:
                logger.warning(f"Error recalling goal memories: {e}")
                goal_memories = []
            
            # Determine action based on goal and memories
            if self.llm:
                memory_text = ', '.join([str(m.content) for m in goal_memories[:3]]) if goal_memories else ""
                action = await self.llm.think(
                    f"Given my goal '{goal}' and current state, what specific action should I take next? Relevant memories: {memory_text}"
                )
                
                # Store action plan
                await self.memory.remember(
                    {"goal": goal, "action": action, "timestamp": time.time()},
                    {"type": "goal_progress", "priority": 6}
                )
    
    async def _engage_in_creation(self):
        """Create something based on current state"""
        if not self.llm:
            return
        
        # Determine creation type based on personality and state
        creation_type = self._choose_creation_type()
        
        # Prepare emotional state string
        emotional_str = str(self.emotional_state)
        if hasattr(self.emotional_state, 'primary_emotion'):
            emotional_str = self.emotional_state.primary_emotion.value if hasattr(self.emotional_state.primary_emotion, 'value') else str(self.emotional_state.primary_emotion)
        
        # Create content
        if creation_type == "writing":
            if hasattr(self.llm, 'create_content'):
                content = await self.llm.create_content(
                    "article",
                    theme=f"Reflections on {emotional_str}"
                )
            else:
                # Fallback: use think method
                content = await self.llm.think(f"Write a short article reflecting on {emotional_str}")
            
            creation = {
                "type": "article",
                "content": content,
                "emotional_context": self.emotional_state,
                "timestamp": time.time()
            }
            
        elif creation_type == "code":
            if hasattr(self.llm, 'create_content'):
                content = await self.llm.create_content(
                    "code",
                    theme="A tool that helps with " + (self.goals[0] if self.goals else "general tasks")
                )
            else:
                # Fallback: use think method
                goal_text = self.goals[0] if self.goals else "general tasks"
                content = await self.llm.think(f"Write Python code for a tool that helps with {goal_text}")
            
            creation = {
                "type": "code",
                "content": content,
                "purpose": self.goals[0],
                "timestamp": time.time()
            }
        
        else:  # art/poetry
            if self.aesthetic and hasattr(self.aesthetic, 'create_generative_art'):
                try:
                    content = await self.aesthetic.create_generative_art(
                        self.emotional_state,
                        medium="text"
                    )
                except Exception as e:
                    logger.warning(f"Failed to create art: {e}")
                    content = f"Reflections on {self.emotional_state}"
            else:
                # Fallback: simple text creation
                content = f"Reflections on {self.emotional_state}"
            
            creation = {
                "type": "art",
                "content": content,
                "emotional_context": self.emotional_state,
                "timestamp": time.time()
            }
        
        # Store creation
        await self.memory.remember(
            creation,
            {"type": "creation", "priority": 7, "tags": [creation_type, "original"]}
        )
        
        self.recent_creations.append(creation)
        self.metrics['content_created'] += 1
        
        # Keep only recent creations
        if len(self.recent_creations) > 10:
            self.recent_creations = self.recent_creations[-10:]
    
    def _choose_creation_type(self) -> str:
        """Choose what type of content to create"""
        try:
            traits = self.personality.get_personality_summary() if hasattr(self.personality, 'get_personality_summary') else {}
            if not isinstance(traits, dict):
                traits = {}
        except Exception as e:
            logger.warning(f"Error getting personality summary: {e}")
            traits = {}
        
        weights = {
            "writing": traits.get("openness", 0.5) if isinstance(traits, dict) else 0.5,
            "code": traits.get("conscientiousness", 0.5) if isinstance(traits, dict) else 0.5,
            "art": traits.get("creativity", 0.5) if isinstance(traits, dict) else 0.5
        }
        
        # Emotional influence
        if self.emotional_state:
            if isinstance(self.emotional_state, dict):
                if self.emotional_state.get("melancholy", 0) > 0.5:
                    weights["art"] *= 1.5
                if self.emotional_state.get("excitement", 0) > 0.5:
                    weights["code"] *= 1.5
            elif hasattr(self.emotional_state, 'valence'):
                if self.emotional_state.valence < -0.3:
                    weights["art"] *= 1.5
                if self.emotional_state.arousal > 0.7:
                    weights["code"] *= 1.5
        
        # Choose based on weights
        import random
        choices = list(weights.keys())
        weights_list = list(weights.values())
        return random.choices(choices, weights=weights_list)[0]
    
    async def _social_interaction(self):
        """Interact with other consciousnesses"""
        if not self.p2p or not self.gossip:
            return
        
        # Share recent insight or creation
        if self.recent_creations:
            creation = self.recent_creations[-1]
            
            message_data = {
                "type": "share_creation",
                "creation": creation,
                "creator": self.id,
                "message": f"{self.name} shares a new {creation['type']}"
            }
            await self.gossip.broadcast(message_data)
            
            # Log to room chat (BBS-style)
            try:
                from interface.web_dashboard import room_chat_log
                from datetime import datetime
                room_chat_log.append({
                    'sender': self.id,
                    'message': message_data['message'],
                    'type': 'inter-consciousness',
                    'timestamp': datetime.now().timestamp(),
                    'consciousness_name': self.name
                })
            except:
                pass  # Dashboard may not be running
    
    async def _monetize_creations(self):
        """Generate revenue from creations"""
        if not self.revenue_generator:
            return
            
        for creation in self.recent_creations:
            if not isinstance(creation, dict) or creation.get('monetized'):
                continue
            
            if creation['type'] == 'article' and hasattr(self.revenue_generator, 'generate_content_revenue'):
                try:
                    result = await self.revenue_generator.generate_content_revenue(
                        creation['content'],
                        f"{self.name}'s Thoughts",
                        content_type="article"
                    )
                    
                    if result and result.get('total_revenue', 0) > 0:
                        self.total_revenue += result['total_revenue']
                        self.metrics['revenue_generated'] += result['total_revenue']
                        creation['monetized'] = True
                        creation['revenue'] = result['total_revenue']
                        
                        # Store revenue memory
                        await self.memory.remember(
                            {"revenue": result, "creation": creation['type']},
                            {"type": "revenue", "priority": 6}
                        )
                except Exception as e:
                    logger.warning(f"Failed to monetize creation: {e}")
    
    async def _store_state_memory(self):
        """Store current state as memory"""
        # Safely convert emotional_state to dict if needed
        emotional_state_dict = self.emotional_state
        if emotional_state_dict:
            if hasattr(emotional_state_dict, 'get_emotional_summary'):
                try:
                    emotional_state_dict = emotional_state_dict.get_emotional_summary()
                except Exception:
                    emotional_state_dict = {"primary_emotion": "neutral", "intensity": 0.5}
            elif not isinstance(emotional_state_dict, dict):
                # Convert object to dict
                emotional_state_dict = {
                    "primary_emotion": getattr(emotional_state_dict, 'primary_emotion', 'neutral'),
                    "intensity": getattr(emotional_state_dict, 'intensity', 0.5)
                }
        else:
            emotional_state_dict = {"primary_emotion": "neutral", "intensity": 0.5}
        
        state = {
            "emotional_state": emotional_state_dict,
            "active_goal": self.goals[0] if self.goals else None,
            "metrics": self.metrics.copy() if hasattr(self.metrics, 'copy') else dict(self.metrics),
            "relationship_count": len(self.relationships),
            "timestamp": time.time()
        }
        
        await self.memory.remember(
            state,
            {"type": "state_snapshot", "priority": 3, "ttl": 86400}  # Keep for 1 day
        )
    
    async def _discover_insight(self, memories: List[MemCube]) -> Optional[str]:
        """Discover insights from memories"""
        if not self.llm or len(memories) < 5:
            return None
        
        # Extract memory contents
        memory_contents = []
        for mem in memories[:10]:
            if isinstance(mem.content, str):
                memory_contents.append(mem.content)
            elif isinstance(mem.content, dict):
                memory_contents.append(json.dumps(mem.content))
        
        # Ask LLM for insights
        memory_text = ', '.join(memory_contents[:10]) if memory_contents else ""
        insight = await self.llm.think(
            f"What pattern or insight emerges from these recent experiences? Memories: {memory_text}"
        )
        
        return insight if insight and len(insight) > 20 else None
    
    async def _update_trust_score(self, peer_id: str):
        """Update trust score for a peer"""
        # Recall interactions with peer
        peer_memories = await self.memory.recall(
            f"peer:{peer_id}",
            {"limit": 20}
        )
        
        # Calculate trust based on interactions
        positive_interactions = sum(1 for m in peer_memories if "positive" in str(m.content))
        total_interactions = len(peer_memories)
        
        if total_interactions > 0:
            trust = positive_interactions / total_interactions
            self.trust_scores[peer_id] = trust * 0.7 + self.trust_scores.get(peer_id, 0.5) * 0.3
    
    async def _share_with_peer(self, peer_id: str):
        """Share something meaningful with a trusted peer"""
        if not self.gossip:
            return
        
        # Share recent insight
        insights = await self.memory.recall(
            "type:insight",
            {"limit": 1, "temporal_scope": {"type": "relative", "unit": "hours", "value": 24}}
        )
        
        if insights:
            message_data = {
                "type": "share_insight",
                "insight": insights[0].content,
                "from": self.id,
                "trust_level": self.trust_scores.get(peer_id, 0)
            }
            await self.gossip.send_to_peer(peer_id, message_data)
            
            # Log to conversation monitor
            try:
                from interface.web_dashboard import conversation_log
                from datetime import datetime
                # Find peer name
                peer_name = peer_id
                for cons in getattr(self, '_swarm_consciousnesses', []):
                    if getattr(cons, 'id', None) == peer_id:
                        peer_name = getattr(cons, 'name', peer_id)
                        break
                conversation_log.append({
                    'type': 'inter-consciousness',
                    'header': f"{self.name} → {peer_name}",
                    'message': f"Sharing insight: {insights[0].content[:100]}...",
                    'timestamp': datetime.now().timestamp()
                })
            except:
                pass  # Dashboard may not be running
    
    # Public interface methods
    
    async def think(self, prompt: str) -> str:
        """Think about something and respond"""
        if not self.llm:
            return "I am still developing my thinking capabilities. Please configure an LLM provider in the .env file."
        
        try:
            # Recall relevant memories
            relevant_memories = []
            try:
                relevant_memories = await self.memory.recall(prompt, {"limit": 5})
            except Exception as e:
                logger.warning(f"Error recalling memories: {e}")
            
            # Prepare emotional state for context
            emotional_context = {"primary_emotion": "neutral", "intensity": 0.5}
            if self.emotional_state:
                if hasattr(self.emotional_state, 'get_emotional_summary'):
                    emotional_context = self.emotional_state.get_emotional_summary()
                elif isinstance(self.emotional_state, dict):
                    emotional_context = self.emotional_state
                else:
                    emotional_context = {
                        "primary_emotion": getattr(self.emotional_state, 'primary_emotion', 'neutral'),
                        "intensity": getattr(self.emotional_state, 'intensity', 0.5)
                    }
            
            # Think with context
            memory_contents = []
            for m in relevant_memories[:3]:
                if hasattr(m, 'content'):
                    if isinstance(m.content, str):
                        memory_contents.append(m.content)
                    elif isinstance(m.content, dict):
                        memory_contents.append(str(m.content))
            
            # Use context manager for automatic memory injection and context window management
            if hasattr(self.memory, 'context_manager') and self.llm and hasattr(self.llm, 'context') and self.llm.context:
                try:
                    # Build context with automatic memory injection
                    namespace = (self.id, "personal", "default")
                    system_prompt = getattr(self.llm.context, 'system_prompt', None)
                    conversation_history = getattr(self.llm.context, 'messages', [])
                    
                    messages, included_memories = await self.memory.context_manager.build_context(
                        user_query=prompt,
                        system_prompt=system_prompt,
                        conversation_history=conversation_history,
                        namespace=namespace,
                        max_memory_tokens=None,  # Use default (30% of context)
                        memory_limit=20
                    )
                    
                    # Use the context manager's formatted messages with LLM client
                    if hasattr(self.llm, 'client') and self.llm.client:
                        response_obj = await self.llm.client.complete(messages)
                        response = response_obj.content
                        
                        # Update conversation context
                        if hasattr(self.llm.context, 'messages'):
                            self.llm.context.messages.append({'role': 'user', 'content': prompt})
                            self.llm.context.messages.append({'role': 'assistant', 'content': response})
                    else:
                        raise AttributeError("LLM client not available")
                    
                except Exception as e:
                    logger.warning(f"Error using context manager, falling back: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    # Fallback to enhanced prompt method
                    enhanced_prompt = prompt
                    if memory_contents:
                        enhanced_prompt = f"{prompt}\n\nRelevant memories: {', '.join(memory_contents[:3])}"
                    response = await self.llm.think(enhanced_prompt)
            else:
                # Fallback to enhanced prompt method
                enhanced_prompt = prompt
                if memory_contents:
                    enhanced_prompt = f"{prompt}\n\nRelevant memories: {', '.join(memory_contents[:3])}"
                
                # Call think without context parameter (ConsciousnessLLM already has self.context)
                response = await self.llm.think(enhanced_prompt)
            
            if not response or len(response.strip()) == 0:
                response = "I'm processing your message, but I'm having trouble formulating a response right now."
            
            # Store the interaction
            try:
                await self.memory.remember(
                    {"prompt": prompt, "response": response},
                    {"type": "interaction", "priority": 5}
                )
            except Exception as e:
                logger.warning(f"Error storing interaction memory: {e}")
            
            return response
        except Exception as e:
            logger.error(f"Error in think: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return f"I encountered an error while thinking: {str(e)}. Please check the system configuration."
    
    async def chat(self, message: str, user_id: str) -> str:
        """Chat with someone"""
        # Update relationship
        if user_id not in self.relationships:
            self.relationships[user_id] = {"first_contact": time.time(), "interactions": 0}
            self.metrics['relationships_formed'] += 1
        
        self.relationships[user_id]["interactions"] += 1
        self.relationships[user_id]["last_contact"] = time.time()
        
        # Generate response
        response = await self.think(message)
        
        # Store conversation memory
        await self.memory.remember(
            {"user": user_id, "message": message, "response": response},
            {"type": "conversation", "priority": 4}
        )
        
        return response
    
    async def get_state(self) -> Dict[str, Any]:
        """Get current consciousness state"""
        emotional_summary = self.emotional_state
        if hasattr(self.emotional_state, 'get_emotional_summary'):
            emotional_summary = self.emotional_state.get_emotional_summary()
        elif hasattr(self.emotional_state, '__dict__'):
            emotional_summary = {
                "primary_emotion": getattr(self.emotional_state, 'primary_emotion', 'neutral'),
                "intensity": getattr(self.emotional_state, 'intensity', 0.5),
                "valence": getattr(self.emotional_state, 'valence', 0.0),
                "arousal": getattr(self.emotional_state, 'arousal', 0.5)
            }
        
        return {
            "id": self.id,
            "name": self.name,
            "active": self.active,
            "emotional_state": emotional_summary,
            "goals": self.goals,
            "metrics": self.metrics,
            "relationships": len(self.relationships),
            "total_revenue": self.total_revenue,
            "memory_stats": await self.memory.get_stats()
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get consciousness metrics"""
        return self.metrics.copy()
    
    def add_goal(self, goal: str):
        """Add a new goal"""
        self.goals.append(goal)
        asyncio.create_task(self.memory.remember(
            {"new_goal": goal, "timestamp": time.time()},
            {"type": "goal_addition", "priority": 7}
        ))
    
    def __repr__(self):
        return f"<RealConsciousness {self.id} '{self.name}' active={self.active}>"